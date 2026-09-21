"""Loan-approval adapter for the governance engine.

Loans already run a mature bespoke workflow (REVIEW_ROLES + per-application
state machine). Rather than replacing it, this adapter records every loan
approval/rejection/cancellation as an ApprovalRequest + ApprovalAction so the
whole governance layer (inbox, audit, reporting) covers loans too.  The loan
domain remains the executor of its own rules.
"""
from governance import workflow
from governance.models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalStatus,
    Decision,
    RequestType,
    RequiredLevel,
)


def record_loan_decision(*, application, user, action, reason="", approved_amount=None):
    """Record an audited governance decision for a loan application.

    ``action`` in {approved, rejected, cancelled}. Returns the request."""
    amount = (
        approved_amount
        if approved_amount is not None
        else (getattr(application, "approved_amount", None) or application.requested_amount)
    )
    request = workflow.create_request(
        group=application.group,
        request_type=RequestType.LOAN_APPLICATION,
        resource=application,
        requester=getattr(application.member, "user", None) or user,
        amount=amount,
        required_level=RequiredLevel.MANUAL,
        required_role="",
        decision=None,
        decision_reason=reason,
        policy_version="loan-review-v1",
        metadata={"loan_application": application.application_number, "action": action},
    )

    action_map = {
        "approved": (ApprovalStatus.APPROVED, ApprovalAction.ACTION_APPROVE),
        "rejected": (ApprovalStatus.REJECTED, ApprovalAction.ACTION_REJECT),
        "cancelled": (ApprovalStatus.CANCELLED, ApprovalAction.ACTION_CANCEL),
    }
    to_status, action_name = action_map.get(action, (ApprovalStatus.COMPLETED, ApprovalAction.ACTION_APPROVE))

    request.status = to_status
    request.save(update_fields=["status", "updated_at"])
    workflow.record_action(
        request=request,
        action=action_name,
        from_status=ApprovalStatus.PENDING,
        to_status=to_status,
        actor=user,
        actor_type=ApprovalAction.ACTOR_HUMAN,
        reason=reason,
    )
    return request