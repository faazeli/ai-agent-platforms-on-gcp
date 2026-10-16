package pipeline_test

import rego.v1

import data.pipeline

good := yaml.unmarshal(`
pipeline:
  stages:
    - stage:
        identifier: deploy_dev
        type: Deployment
        spec:
          environment: {environmentRef: dev}
          execution:
            steps:
              - stepGroup:
                  steps:
                    - step: {type: K8sCanaryDeploy, identifier: canary_deploy}
                    - step: {type: ShellScript, identifier: canary_evals}
        failureStrategies:
          - onFailure: {errors: [AllErrors], action: {type: StageRollback}}
    - stage: {identifier: approve_prod, type: Approval}
    - stage:
        identifier: deploy_prod
        type: Deployment
        spec:
          environment: {environmentRef: prod}
          execution:
            steps:
              - step: {type: K8sCanaryDeploy, identifier: canary_deploy}
              - step: {type: Verify, identifier: verify}
        failureStrategies:
          - onFailure: {errors: [AllErrors], action: {type: StageRollback}}
`)

test_reference_shape_passes if {
	count(pipeline.deny) == 0 with input as good
}

test_prod_without_approval_is_denied if {
	no_approval := json.patch(good, [{"op": "remove", "path": "/pipeline/stages/1"}])
	some msg in pipeline.deny with input as no_approval
	contains(msg, "without an earlier Approval")
}

test_approval_after_prod_does_not_count if {
	reordered := {"pipeline": {"stages": [good.pipeline.stages[0], good.pipeline.stages[2], good.pipeline.stages[1]]}}
	some msg in pipeline.deny with input as reordered
	contains(msg, "deploy_prod")
}

test_missing_rollback_is_denied if {
	no_rollback := json.patch(good, [{"op": "remove", "path": "/pipeline/stages/2/stage/failureStrategies"}])
	some msg in pipeline.deny with input as no_rollback
	contains(msg, "StageRollback")
}

test_unjudged_canary_is_denied if {
	no_verify := json.patch(good, [{"op": "remove", "path": "/pipeline/stages/2/stage/spec/execution/steps/1"}])
	some msg in pipeline.deny with input as no_verify
	contains(msg, "neither the agent eval gate")
}

test_dev_without_eval_gate_is_denied if {
	no_evals := json.patch(good, [{
		"op": "replace",
		"path": "/pipeline/stages/0/stage/spec/execution/steps/0/stepGroup/steps/1",
		"value": {"type": "Verify", "identifier": "verify"},
	}])
	some msg in pipeline.deny with input as no_evals
	contains(msg, "agent eval gate (step identifier canary_evals)")
}
