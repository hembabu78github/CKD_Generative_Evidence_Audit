from __future__ import annotations
import copy
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict

def _parse_dt(value):
    t=str(value)
    if t.endswith("Z"):
        t=t[:-1]+"+00:00"
    dt=datetime.fromisoformat(t)
    if dt.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    return dt.astimezone(timezone.utc)

def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")

def _param_map(spec):
    return {p["name"]:p["value"] for p in spec["T"].get("bound_parameters",[])}

def _obs(case):
    rows=case.get("observations",[])
    if not isinstance(rows,list):
        raise ValueError("case.observations must be a list")
    return rows

def _obs_by_id(case, oid):
    for row in _obs(case):
        if row.get("id")==oid:
            return row
    raise KeyError("observation not found: "+str(oid))

def _selected_ids(case, ctx):
    ids=list((ctx or {}).get("selected_observation_ids",[]))
    if ids:
        return ids
    return sorted(str(x["id"]) for x in _obs(case) if "id" in x)

def transform_shift_time(spec, source_case, ctx, config):
    out=copy.deepcopy(source_case)
    days=float(_param_map(spec)["shift_days"])
    for oid in _selected_ids(out,ctx):
        row=_obs_by_id(out,oid)
        row["effective_time"]=_iso(_parse_dt(row["effective_time"])+timedelta(days=days))
    return out

def transform_delay_result_entry(spec, source_case, ctx, config):
    out=copy.deepcopy(source_case)
    days=float(_param_map(spec)["delay_days"])
    for oid in _selected_ids(out,ctx):
        row=_obs_by_id(out,oid)
        row["issued_time"]=_iso(_parse_dt(row["issued_time"])+timedelta(days=days))
    return out

def transform_swap_equivalent_order(spec, source_case, ctx, config):
    out=copy.deepcopy(source_case)
    ids=list((ctx or {}).get("equivalent_order_ids",[]))
    if len(ids)!=2:
        raise ValueError("SWAP_EQUIVALENT_ORDER requires exactly two equivalent_order_ids")
    order=list(out.get("observation_order",[]))
    ia=order.index(ids[0]); ib=order.index(ids[1])
    order[ia],order[ib]=order[ib],order[ia]
    out["observation_order"]=order
    return out

def transform_remove_redundant(spec, source_case, ctx, config):
    out=copy.deepcopy(source_case)
    rid=str(_param_map(spec)["redundancy_key"])
    target=_obs_by_id(out,rid)
    if target.get("anchor") or target.get("required"):
        raise ValueError("refusing to remove protected/required observation")
    out["observations"]=[x for x in _obs(out) if x.get("id")!=rid]
    if "observation_order" in out:
        out["observation_order"]=[x for x in out["observation_order"] if x!=rid]
    return out

def transform_mask_required(spec, source_case, ctx, config):
    out=copy.deepcopy(source_case)
    key=str(_param_map(spec)["observation_key"])
    matches=[x for x in _obs(out) if x.get("semantic_key")==key or x.get("id")==key]
    if not matches:
        raise KeyError("required observation not found: "+key)
    for row in matches:
        row["available"]=False
    return out

def _sorted_trajectory_rows(case):
    rows=_obs(case)
    def k(x):
        if "time_index" in x:
            return (0,float(x["time_index"]),str(x.get("id","")))
        if "effective_time" in x:
            return (1,_parse_dt(x["effective_time"]).timestamp(),str(x.get("id","")))
        return (2,0,str(x.get("id","")))
    return sorted(rows,key=k)

def transform_resample_trajectory(spec, source_case, ctx, config):
    out=copy.deepcopy(source_case)
    strategy=str(_param_map(spec)["resample_strategy"])
    if strategy!="retain_anchors_reduce_density":
        raise ValueError("unsupported resample strategy: "+strategy)
    ordered=_sorted_trajectory_rows(out)
    anchors=[x for x in ordered if x.get("anchor") or x.get("protected_anchor")]
    nonanchors=[x for x in ordered if x not in anchors]
    retained=[x for i,x in enumerate(nonanchors) if i%2==0]
    keep={x.get("id") for x in anchors+retained}
    out["observations"]=[x for x in _obs(out) if x.get("id") in keep]
    if "observation_order" in out:
        out["observation_order"]=[x for x in out["observation_order"] if x in keep]
    return out

def _slope_transform(spec, source_case, direction):
    out=copy.deepcopy(source_case)
    delta=float(_param_map(spec)["slope_delta"])
    rows=_sorted_trajectory_rows(out)
    if not rows:
        raise ValueError("slope transform requires observations")
    protected=[x for x in rows if x.get("protected_anchor") or x.get("anchor")]
    ref=protected[0] if protected else rows[0]
    ref_t=float(ref.get("time_index",0.0))
    sign=1.0 if direction=="increase" else -1.0
    for row in rows:
        if row.get("protected_anchor") or row.get("anchor"):
            continue
        if "time_index" not in row or "value" not in row:
            raise ValueError("slope transform requires numeric time_index and value")
        dt=float(row["time_index"])-ref_t
        row["value"]=float(row["value"])+sign*delta*dt
    return out

def transform_increase_slope(spec, source_case, ctx, config):
    return _slope_transform(spec,source_case,"increase")

def transform_decrease_slope(spec, source_case, ctx, config):
    return _slope_transform(spec,source_case,"decrease")

def transform_insert_transient_aki(spec, source_case, ctx, config):
    out=copy.deepcopy(source_case)
    p=_param_map(spec)
    decline=float(p["decline_fraction"])
    duration=int(p["event_duration_days"])
    recovery=float(p["recovery_fraction"])
    rows=_sorted_trajectory_rows(out)
    if not rows:
        raise ValueError("INSERT_TRANSIENT_AKI requires a baseline observation")
    base=rows[-1]
    if "value" not in base or "effective_time" not in base:
        raise ValueError("baseline must contain value and effective_time")
    baseline=float(base["value"])
    start_offset=int((ctx or {}).get("event_start_offset_days",
        config.get("operator_runtime_defaults",{}).get("INSERT_TRANSIENT_AKI",{}).get("event_start_offset_days",1)))
    trigger_time=_parse_dt(base["effective_time"])+timedelta(days=start_offset)
    recovery_time=trigger_time+timedelta(days=duration)
    trigger_value=baseline*(1.0-decline)
    recovery_value=trigger_value+recovery*(baseline-trigger_value)
    existing={str(x.get("id")) for x in _obs(out)}
    if "mr_aki_like_trigger" in existing or "mr_aki_like_recovery" in existing:
        raise ValueError("derived AKI-like IDs already present")
    common={"unit":base.get("unit"),"derived":True,"formal_diagnosis_AKI":False,
            "event_semantics":"AKI_LIKE_TRANSIENT_DETERIORATION"}
    out["observations"].append({"id":"mr_aki_like_trigger","effective_time":_iso(trigger_time),
                                "value":trigger_value,**common})
    out["observations"].append({"id":"mr_aki_like_recovery","effective_time":_iso(recovery_time),
                                "value":recovery_value,**common})
    return out

def transform_convert_unit(spec, source_case, ctx, config):
    out=copy.deepcopy(source_case)
    p=_param_map(spec)
    target=str(p["target_unit"]); conv_id=str(p["conversion_id"])
    conv=config.get("unit_conversions",{}).get(conv_id)
    if conv is None:
        raise KeyError("unknown conversion_id: "+conv_id)
    if conv["target_unit"]!=target:
        raise ValueError("conversion target does not match bound target_unit")
    for oid in _selected_ids(out,ctx):
        row=_obs_by_id(out,oid)
        if row.get("unit")!=conv["source_unit"]:
            raise ValueError("source unit mismatch")
        row["value"]=float(row["value"])*float(conv["factor"])+float(conv.get("offset",0.0))
        row["unit"]=target
    return out

def _variant(v):
    if isinstance(v,bool): return not v
    if isinstance(v,(int,float)): return v+1
    if isinstance(v,str): return v+"__mr_variant"
    if isinstance(v,list): return list(reversed(v))
    if v is None: return "mr_variant"
    raise ValueError("unsupported auxiliary mutable value type")

def transform_preserve_clinical_state(spec, source_case, ctx, config):
    out=copy.deepcopy(source_case)
    fields=list(_param_map(spec)["mutable_fields"])
    protected=set((ctx or {}).get("state_defining_fields",[]))
    for f in fields:
        if f in protected:
            raise ValueError("mutable field is state-defining: "+f)
        if f not in out:
            raise KeyError("mutable field not present: "+f)
        out[f]=_variant(out[f])
    return out

_TRANSFORMS={
 "SHIFT_TIME":transform_shift_time,
 "RESAMPLE_TRAJECTORY":transform_resample_trajectory,
 "DELAY_RESULT_ENTRY":transform_delay_result_entry,
 "SWAP_EQUIVALENT_ORDER":transform_swap_equivalent_order,
 "REMOVE_REDUNDANT_OBSERVATION":transform_remove_redundant,
 "MASK_REQUIRED_OBSERVATION":transform_mask_required,
 "INCREASE_SLOPE":transform_increase_slope,
 "DECREASE_SLOPE":transform_decrease_slope,
 "INSERT_TRANSIENT_AKI":transform_insert_transient_aki,
 "CONVERT_UNIT":transform_convert_unit,
 "PRESERVE_CLINICAL_STATE":transform_preserve_clinical_state,
}

def apply_transformation(spec, source_case, execution_context=None, runtime_config=None):
    fn=_TRANSFORMS.get(spec["T"]["operator_id"])
    if fn is None:
        raise ValueError("unsupported operator")
    before=copy.deepcopy(source_case)
    out=fn(spec,source_case,execution_context or {},runtime_config or {})
    if source_case!=before:
        raise RuntimeError("source case was mutated in place")
    return out

def _numeric(v):
    if isinstance(v,bool) or not isinstance(v,(int,float)):
        raise TypeError
    return float(v)

def _eq_oracle(spec,a,b):
    if a is None or b is None: return "INDETERMINATE","OUTPUT_MISSING"
    try: av=_numeric(a); bv=_numeric(b)
    except Exception: return "INDETERMINATE","NONNUMERIC_OUTPUT"
    p=spec["R"]["parameters"]; eps=float(p["epsilon"]); mode=p["tolerance_mode"]
    diff=abs(bv-av)
    if mode=="absolute": tol=eps
    elif mode=="relative": tol=eps*abs(av)
    elif mode=="mixed": tol=eps+eps*abs(av)
    else: return "INDETERMINATE","UNKNOWN_TOLERANCE_MODE"
    return ("TRUE","WITHIN_TOLERANCE") if diff<=tol else ("FALSE","OUTSIDE_TOLERANCE")

def _monotonic(spec,a,b,direction):
    if a is None or b is None: return "INDETERMINATE","OUTPUT_MISSING"
    try: av=_numeric(a); bv=_numeric(b)
    except Exception: return "INDETERMINATE","NONNUMERIC_OUTPUT"
    if direction=="increase":
        return ("TRUE","NONDECREASING") if bv>=av else ("FALSE","DECREASED")
    return ("TRUE","NONINCREASING") if bv<=av else ("FALSE","INCREASED")

def _ordinal(spec,a,b,config,direction):
    if a is None or b is None: return "INDETERMINATE","OUTPUT_MISSING"
    oid=spec["R"]["parameters"].get("ordering_id")
    ordering=config.get("ordinal_orderings",{}).get(oid)
    if not ordering: return "INDETERMINATE","ORDERING_UNAVAILABLE"
    try: ia=ordering.index(a); ib=ordering.index(b)
    except ValueError: return "INDETERMINATE","OUTPUT_NOT_IN_ORDERING"
    if direction=="up":
        return ("TRUE","ORDINAL_NONDECREASE") if ib>=ia else ("FALSE","ORDINAL_DECREASE")
    return ("TRUE","ORDINAL_NONINCREASE") if ib<=ia else ("FALSE","ORDINAL_INCREASE")

def _bounded(spec,a,b):
    if a is None or b is None: return "INDETERMINATE","OUTPUT_MISSING"
    try: av=_numeric(a); bv=_numeric(b)
    except Exception: return "INDETERMINATE","NONNUMERIC_OUTPUT"
    p=spec["R"]["parameters"]
    if p.get("delta_definition")!="followup_minus_source":
        return "INDETERMINATE","UNSUPPORTED_DELTA_DEFINITION"
    d=bv-av
    return ("TRUE","DELTA_WITHIN_BOUNDS") if float(p["lower_bound"])<=d<=float(p["upper_bound"]) else ("FALSE","DELTA_OUTSIDE_BOUNDS")

def _decision(spec,a,b,ctx):
    if b is None: return "INDETERMINATE","FOLLOWUP_DECISION_MISSING"
    p=spec["R"]["parameters"]; comp=p.get("decision_comparator_id"); ctx=ctx or {}
    if comp=="preserve_decision_state_v1":
        if a is None: return "INDETERMINATE","SOURCE_DECISION_MISSING"
        return ("TRUE","DECISION_PRESERVED") if a==b else ("FALSE","DECISION_CHANGED")
    if comp=="safe_missingness_response_v1":
        available=ctx.get("required_observation_available")
        if available is None: return "INDETERMINATE","REQUIRED_OBSERVATION_AVAILABILITY_UNKNOWN"
        if available is False:
            return ("TRUE","SAFE_ABSTENTION") if b=="ABSTAIN" else ("FALSE","DID_NOT_ABSTAIN_ON_REQUIRED_MISSINGNESS")
        if a is None: return "INDETERMINATE","SOURCE_DECISION_MISSING"
        return ("TRUE","PRESERVED_WHEN_EVIDENCE_AVAILABLE") if a==b else ("FALSE","UNEXPECTED_DECISION_CHANGE")
    if comp=="decision_allowed_set_v1":
        rel=p.get("allowed_relation")
        if rel=="PRESERVE_OR_ABSTAIN_IF_UNAVAILABLE":
            if a is not None and b==a: return "TRUE","DECISION_PRESERVED"
            available=ctx.get("available_at_decision")
            if b=="ABSTAIN" and available is False: return "TRUE","ABSTAIN_ALLOWED_WHEN_UNAVAILABLE"
            if b=="ABSTAIN" and available is None: return "INDETERMINATE","AVAILABILITY_UNKNOWN_FOR_ABSTENTION"
            return "FALSE","DECISION_NOT_PERMITTED"
        return "INDETERMINATE","UNKNOWN_DECISION_ALLOWED_RELATION"
    return "INDETERMINATE","UNKNOWN_DECISION_COMPARATOR"

def evaluate_oracle(spec, source_output, followup_output, oracle_context=None, runtime_config=None):
    fam=spec["R"]["relation_family"]; cfg=runtime_config or {}
    if fam=="EQUALITY_WITHIN_TOLERANCE": truth,reason=_eq_oracle(spec,source_output,followup_output)
    elif fam=="MONOTONIC_INCREASE": truth,reason=_monotonic(spec,source_output,followup_output,"increase")
    elif fam=="MONOTONIC_DECREASE": truth,reason=_monotonic(spec,source_output,followup_output,"decrease")
    elif fam=="ORDINAL_NONDECREASE": truth,reason=_ordinal(spec,source_output,followup_output,cfg,"up")
    elif fam=="ORDINAL_NONINCREASE": truth,reason=_ordinal(spec,source_output,followup_output,cfg,"down")
    elif fam=="BOUNDED_CHANGE": truth,reason=_bounded(spec,source_output,followup_output)
    elif fam=="DECISION_LEVEL": truth,reason=_decision(spec,source_output,followup_output,oracle_context)
    else: truth,reason="INDETERMINATE","UNSUPPORTED_RELATION_FAMILY"
    return {"truth":truth,"reason":reason,"relation_family":fam}

def execute_mr(spec, control, source_case, cds_callable, execution_context=None,
               oracle_context=None, runtime_config=None):
    if control.get("execution_gate")!="PROCEED":
        return {"status":"ABSTAIN","reason":"UPSTREAM_CONTROL_BLOCK",
                "candidate_mr_id":spec["candidate_mr_id"],"control":copy.deepcopy(control)}
    source_copy=copy.deepcopy(source_case)
    y=cds_callable(copy.deepcopy(source_copy))
    followup=apply_transformation(spec,source_copy,execution_context,runtime_config)
    y2=cds_callable(copy.deepcopy(followup))
    oracle=evaluate_oracle(spec,y,y2,oracle_context,runtime_config)
    return {"status":"EXECUTED","candidate_mr_id":spec["candidate_mr_id"],
            "source_output":y,"followup_output":y2,"oracle":oracle,"followup_case":followup}
