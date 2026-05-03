% Pattern 1 — Operator allocation optimization
%
% Inputs:
%   n_ops              : number of operations (rows in operations grid)
%   sam_min            : standard allowed minutes per piece, per op
%   grade_pct          : operator efficiency 0..100, per op
%   demand_pcs_per_day : effective daily demand at this op (pcs/day)
%                        — caller pre-scales by product mix + bundle size.
%   daily_planned_minutes : minutes available per day (e.g. 8*60 = 480)
%   max_operators_per_op  : upper bound per station (caller policy)
%   total_operators_budget: optional cap on sum(operators) (-1 = no cap)
%
% Decision variables:
%   operators[i] in 1..max_operators_per_op
%
% Constraint:
%   For each op i, achievable pcs/day must meet demand:
%     operators[i] * (60 / sam_min[i]) * (grade_pct[i] / 100)
%       * (daily_planned_minutes / 60)
%     >= demand_pcs_per_day[i]
%
% Objective:
%   Minimize sum(operators); tie-break by minimizing the maximum
%   utilization headroom variation across stations.
%
% Output:
%   JSON line: { "operators":[...], "total_operators": K,
%                "predicted_pcs_per_day_per_op":[...], "objective": K }

% (No `include "globals.mzn"` — this model uses only core builtins
% (forall, sum, int2float, show, show_float, concat). Including
% globals.mzn triggers a stdlib type-error on the apt-shipped
% MiniZinc 2.7 in the Render Docker image even when no global
% constraint is referenced.)

% --- inputs --------------------------------------------------------------

int: n_ops;

array[1..n_ops] of float: sam_min;
array[1..n_ops] of int: grade_pct;
array[1..n_ops] of int: demand_pcs_per_day;

int: daily_planned_minutes;
int: max_operators_per_op;
int: total_operators_budget;  % -1 means no upper cap

% --- decision variable ---------------------------------------------------

array[1..n_ops] of var 1..max_operators_per_op: operators;

% --- derived: predicted throughput per op (pcs/day) ----------------------
% Scale by 100 (grade_pct integer percent → fraction). Multiply by
% daily_planned_minutes / sam_min and operators.
%
% predicted = operators * (60 / sam_min) * (grade_pct/100) * (planned/60)
%           = operators * (planned * grade_pct) / (sam_min * 100)
%
% MiniZinc int division floors; we keep the formula as float for the
% capacity check, then publish a rounded integer in the output.

array[1..n_ops] of var float: predicted_pcs_per_day =
  [ int2float(operators[i]) * int2float(daily_planned_minutes)
    * int2float(grade_pct[i]) / (sam_min[i] * 100.0)
    | i in 1..n_ops ];

% --- demand-coverage constraint -----------------------------------------

constraint forall (i in 1..n_ops) (
  predicted_pcs_per_day[i] >= int2float(demand_pcs_per_day[i])
);

% --- optional total-operators budget ------------------------------------

constraint
  if total_operators_budget >= 0 then
    sum(operators) <= total_operators_budget
  else
    true
  endif;

% --- objective: minimize total operators --------------------------------

var int: total_operators = sum(operators);
solve minimize total_operators;

% --- structured JSON output ---------------------------------------------
%
% MiniZinc 2.5+ has `show_json` for primitives but not directly for
% arrays of var int — emit hand-rolled JSON instead. Concatenated lines
% form a single { ... } object on one line so the runner's parser picks
% it up.

output [
  "{",
  "\"operators\": [",
    concat([ if i = 1 then show(operators[i])
             else "," ++ show(operators[i]) endif
             | i in 1..n_ops ]),
  "],",
  "\"total_operators\": ", show(total_operators), ",",
  "\"predicted_pcs_per_day_per_op\": [",
    concat([ if i = 1 then show_float(0, 2, predicted_pcs_per_day[i])
             else "," ++ show_float(0, 2, predicted_pcs_per_day[i]) endif
             | i in 1..n_ops ]),
  "],",
  "\"objective\": ", show(total_operators),
  "}\n"
];
