# apps/tasks/state_machine.py
from apps.tasks.models import MainTask, SubTask

# Allowed transitions for everyone
VALID_TRANSITIONS = {
    MainTask.Status.UNASSIGNED : [MainTask.Status.ASSIGNED],
    MainTask.Status.ASSIGNED   : [MainTask.Status.IN_PROGRESS],
    MainTask.Status.IN_PROGRESS: [MainTask.Status.COMPLETED],
    MainTask.Status.COMPLETED  : [],  # terminal state
}

# Transitions only a Manager can do
MANAGER_ONLY_TRANSITIONS = {
    MainTask.Status.ASSIGNED   : [MainTask.Status.UNASSIGNED],
    MainTask.Status.IN_PROGRESS: [MainTask.Status.UNASSIGNED, MainTask.Status.ASSIGNED],
    MainTask.Status.COMPLETED  : [MainTask.Status.IN_PROGRESS],
}


def get_allowed_transitions(current_status, is_manager=False):
    transitions = list(VALID_TRANSITIONS.get(current_status, []))
    if is_manager:
        transitions += MANAGER_ONLY_TRANSITIONS.get(current_status, [])
    return transitions


def validate_transition(current_status, new_status, is_manager=False):
    """
    Returns (True, None) if the transition is valid.
    Returns (False, error_message) if not.
    """
    if current_status == new_status:
        return False, f'Task is already in {new_status} status.'

    allowed = get_allowed_transitions(current_status, is_manager)

    if new_status not in allowed:
        # Give a specific message for common mistakes
        if (current_status == MainTask.Status.UNASSIGNED
                and new_status == MainTask.Status.COMPLETED):
            return False, (
                'A task cannot move from UNASSIGNED directly to COMPLETED. '
                'It must go through ASSIGNED → IN_PROGRESS first.'
            )
        if (current_status != MainTask.Status.IN_PROGRESS
                and new_status == MainTask.Status.COMPLETED):
            return False, (
                'A task must be IN_PROGRESS before it can be marked COMPLETED.'
            )
        if new_status == MainTask.Status.UNASSIGNED and not is_manager:
            return False, (
                'Only a Manager can move a task back to UNASSIGNED.'
            )

        allowed_display = [s for s in allowed] or ['none']
        return False, (
            f'Invalid transition: {current_status} → {new_status}. '
            f'Allowed from {current_status}: {", ".join(allowed_display)}.'
        )

    return True, None

# ─── SubTask State Machine ────────────────────────────────────

SUBTASK_VALID_TRANSITIONS = {
    SubTask.Status.NOT_STARTED    : [SubTask.Status.IN_PROGRESS],
    SubTask.Status.IN_PROGRESS    : [SubTask.Status.AWAITING_REVIEW],
    SubTask.Status.AWAITING_REVIEW: [SubTask.Status.COMPLETED, SubTask.Status.IN_PROGRESS],
    SubTask.Status.COMPLETED      : [],  # terminal
}

# Department Head can move back or override
SUBTASK_HEAD_ONLY_TRANSITIONS = {
    SubTask.Status.IN_PROGRESS    : [SubTask.Status.NOT_STARTED],
    SubTask.Status.AWAITING_REVIEW: [SubTask.Status.NOT_STARTED],
    SubTask.Status.COMPLETED      : [SubTask.Status.IN_PROGRESS],
}


def validate_subtask_transition(current_status, new_status, is_head=False):
    """
    Returns (True, None) if valid.
    Returns (False, error_message) if not.
    """
    if current_status == new_status:
        return False, f'SubTask is already {new_status}.'

    allowed = list(SUBTASK_VALID_TRANSITIONS.get(current_status, []))
    if is_head:
        allowed += SUBTASK_HEAD_ONLY_TRANSITIONS.get(current_status, [])

    if new_status not in allowed:
        if new_status == SubTask.Status.COMPLETED and current_status != SubTask.Status.AWAITING_REVIEW:
            return False, (
                'A subtask must be AWAITING_REVIEW before it can be marked COMPLETED.'
            )
        allowed_display = [s for s in allowed] or ['none']
        return False, (
            f'Invalid transition: {current_status} → {new_status}. '
            f'Allowed: {", ".join(allowed_display)}.'
        )

    return True, None