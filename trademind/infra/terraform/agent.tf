# Ops agent (docs/AGENT.md): the trademind-agent workflow, running on main in this repository, gets
# one-hour credentials for a role that can only call Claude models on Bedrock. Nothing else in the
# account is reachable from the agent: the runner user is also blocked from the instance metadata service.
#
# The Bedrock fallback is off unless agent_bedrock_monthly_usd > 0: at 0 the role has no permissions
# at all. Above 0, an AWS Budgets action attaches a deny policy to the role once the month's Bedrock
# spend passes the agent's cap plus the research cap. This is the hard limit; the spend file on the
# runner is only a convenience the agent could edit. Budgets data lags by some hours, so a day's
# spend can overshoot; each run is also capped at budget_usd.

data "aws_caller_identity" "current" {}

resource "aws_iam_openid_connect_provider" "github" {
  count           = var.create_github_oidc_provider ? 1 : 0
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1", "1c58a3a8518e8759bf075b76b750d4f2df264fcd"]
}

locals {
  github_oidc_provider_arn = (
    var.create_github_oidc_provider
    ? aws_iam_openid_connect_provider.github[0].arn
    : "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
  )
}

data "aws_iam_policy_document" "assume_github_agent" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "agent" {
  name_prefix          = "trademind-agent-"
  assume_role_policy   = data.aws_iam_policy_document.assume_github_agent.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "agent" {
  statement {
    sid     = "ClaudeOnBedrock"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:aws:bedrock:*:*:inference-profile/*anthropic.claude-*",
      "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
    ]
  }
  statement {
    sid       = "InferenceProfiles"
    actions   = ["bedrock:ListInferenceProfiles", "bedrock:GetInferenceProfile"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "agent" {
  count       = var.agent_bedrock_monthly_usd > 0 ? 1 : 0
  name_prefix = "trademind-agent-"
  role        = aws_iam_role.agent.id
  policy      = data.aws_iam_policy_document.agent.json
}

resource "aws_iam_policy" "agent_bedrock_stop" {
  count       = var.agent_bedrock_monthly_usd > 0 ? 1 : 0
  name_prefix = "trademind-agent-bedrock-stop-"
  description = "Attached by the AWS budget action when the month's Bedrock spend passes the cap."
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Deny", Action = "bedrock:*", Resource = "*" }]
  })
}

data "aws_iam_policy_document" "assume_budgets" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "budget_action" {
  count              = var.agent_bedrock_monthly_usd > 0 ? 1 : 0
  name_prefix        = "trademind-budget-action-"
  assume_role_policy = data.aws_iam_policy_document.assume_budgets.json
}

resource "aws_iam_role_policy" "budget_action" {
  count       = var.agent_bedrock_monthly_usd > 0 ? 1 : 0
  name_prefix = "trademind-budget-action-"
  role        = aws_iam_role.budget_action[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"]
      Resource = aws_iam_role.agent.arn
    }]
  })
}

resource "aws_budgets_budget" "bedrock" {
  count        = var.agent_bedrock_monthly_usd > 0 ? 1 : 0
  name         = "trademind-bedrock"
  budget_type  = "COST"
  limit_amount = tostring(var.agent_bedrock_monthly_usd + var.research_bedrock_monthly_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "Service"
    values = ["Amazon Bedrock"]
  }
}

resource "aws_budgets_budget_action" "agent_bedrock_stop" {
  count              = var.agent_bedrock_monthly_usd > 0 ? 1 : 0
  budget_name        = aws_budgets_budget.bedrock[0].name
  action_type        = "APPLY_IAM_POLICY"
  approval_model     = "AUTOMATIC"
  notification_type  = "ACTUAL"
  execution_role_arn = aws_iam_role.budget_action[0].arn

  action_threshold {
    action_threshold_type  = "PERCENTAGE"
    action_threshold_value = 100
  }

  definition {
    iam_action_definition {
      policy_arn = aws_iam_policy.agent_bedrock_stop[0].arn
      roles      = [aws_iam_role.agent.name]
    }
  }

  subscriber {
    address           = var.alert_email
    subscription_type = "EMAIL"
  }
}
