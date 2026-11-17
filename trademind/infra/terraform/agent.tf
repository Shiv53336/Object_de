# Ops agent (docs/AGENT.md): the trademind-agent workflow, running on main in this repository, gets
# one-hour credentials for a role that can only call Claude models on Bedrock. Nothing else in the
# account is reachable from the agent: the runner user is also blocked from the instance metadata service.

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
  name_prefix = "trademind-agent-"
  role        = aws_iam_role.agent.id
  policy      = data.aws_iam_policy_document.agent.json
}
