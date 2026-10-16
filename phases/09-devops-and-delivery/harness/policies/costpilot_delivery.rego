# Harness Policy as Code (OPA): guardrails every CostPilot pipeline must keep,
# whoever edits it. Attach to the "On Save" and "On Run" events of pipelines in
# Harness → Project settings → Policies. Same intent as branch protection plus the
# GitHub "production" environment in Track A, but enforced on the pipeline itself.
package pipeline

import rego.v1

stages := [s.stage | some s in input.pipeline.stages; s.stage]

deploys_to(stage, env) if {
	stage.type == "Deployment"
	stage.spec.environment.environmentRef == env
}

# All steps in a stage, including those inside step groups and parallel blocks.
steps(stage) := [node.step |
	walk(stage.spec.execution.steps, [_, node])
	is_object(node)
	node.step
]

# 1. Production deploys need a human approval stage earlier in the pipeline.
deny contains msg if {
	some i, stage in stages
	deploys_to(stage, "prod")
	not approval_before(i)
	msg := sprintf("stage '%s' deploys to prod without an earlier Approval stage", [stage.identifier])
}

approval_before(i) if {
	some j, stage in stages
	j < i
	stage.type == "Approval"
}

# 2. Every deployment stage rolls itself back on failure.
deny contains msg if {
	some stage in stages
	stage.type == "Deployment"
	not stage_rollback(stage)
	msg := sprintf("stage '%s' must use the StageRollback failure strategy", [stage.identifier])
}

stage_rollback(stage) if {
	some strategy in stage.failureStrategies
	strategy.onFailure.action.type == "StageRollback"
}

# 3. A canary must be judged: by the agent eval gate, or by Harness CV.
deny contains msg if {
	some stage in stages
	some step in steps(stage)
	step.type == "K8sCanaryDeploy"
	not judged(stage)
	msg := sprintf("stage '%s' runs a canary with neither the agent eval gate nor a Verify step", [stage.identifier])
}

judged(stage) if {
	some step in steps(stage)
	step.identifier == "canary_evals"
}

judged(stage) if {
	some step in steps(stage)
	step.type == "Verify"
}

# 4. Dev, which serves the eval set's sample data, must run the agent eval gate.
deny contains msg if {
	some stage in stages
	deploys_to(stage, "dev")
	not eval_gate(stage)
	msg := sprintf("stage '%s' must run the agent eval gate (step identifier canary_evals)", [stage.identifier])
}

eval_gate(stage) if {
	some step in steps(stage)
	step.identifier == "canary_evals"
}
