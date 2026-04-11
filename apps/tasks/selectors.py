# apps/tasks/selectors.py
"""
Selector functions — encapsulate complex query logic.
Views call these functions and receive ready data.
Keeps views thin and queries testable in isolation.
"""
from datetime     import timedelta, date
from django.utils import timezone
from django.core.cache import cache
from django.db.models import (
    Count, Q, Avg, FloatField, Value, ExpressionWrapper,
    Case, When, F
)
from django.db.models.functions import Cast, Round, Coalesce

from apps.tasks.models    import MainTask, SubTask, Request
from apps.accounts.models import Employee

WARNING_THRESHOLD = 30  # delay_rate % that triggers a warning

# Cache TTL configurations (seconds)
CACHE_TTL_DASHBOARD = 300  # 5 minutes
CACHE_TTL_EMPLOYEE_DASHBOARD = 60  # 1 minute (more volatile)


def invalidate_dashboard_cache():
    """Invalidate all dashboard-related cache keys."""
    # Pattern-based invalidation (requires django-redis)
    try:
        cache.delete_pattern("dashboard:*")
        cache.delete_pattern("performance:*")
    except AttributeError:
        # Fallback for non-redis caches
        pass


# ─── Manager Dashboard ────────────────────────────────────────

def get_manager_dashboard(today=None):
    """
    Returns a single dict consumed by ManagerDashboardSerializer.
    All aggregations run in the database — no Python loops.
    Includes defensive caching for high-traffic endpoints.
    """
    if today is None:
        today = timezone.now().date()
    
    # Cache key includes date to auto-invalidate on day change
    cache_key = f"dashboard:manager:{today}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    active_statuses = ['unassigned', 'assigned', 'in_progress']

    # ── KPIs ──────────────────────────────────────────────────
    task_agg = MainTask.objects.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        active=Count('id', filter=Q(status__in=active_statuses)),
        overdue=Count('id', filter=Q(
            status__in=active_statuses,
            due_date__lt=today,
        )),
    )

    total    = task_agg['total'] or 0
    active   = task_agg['active'] or 0
    overdue  = task_agg['overdue'] or 0
    completed = task_agg['completed'] or 0

    overall_progress = round((completed / total * 100), 1) if total > 0 else 0.0
    non_overdue      = active - overdue
    dept_efficiency  = round((non_overdue / active * 100), 1) if active > 0 else 100.0

    # ── Employee stats via custom manager ─────────────────────
    employees_qs = Employee.objects.with_performance_stats(today)

    # critical_delays: employees whose delay_rate > WARNING_THRESHOLD
    critical_delays = employees_qs.filter(
        delay_rate__gt=WARNING_THRESHOLD
    ).count()

    # Employee scorecard aggregates
    emp_agg = employees_qs.aggregate(
        avg_completion=Avg('completion_rate'),
        avg_delay=Avg('delay_rate'),
        total_employees=Count('id'),
    )
    avg_completion   = round(emp_agg['avg_completion'] or 0.0, 1)
    avg_delay_emp    = round(emp_agg['avg_delay'] or 0.0, 1)
    quality_score    = round(max(0, 100 - avg_delay_emp), 1)
    total_employees  = emp_agg['total_employees'] or 0

    # ── Warning List ──────────────────────────────────────────
    warning_list = list(
        employees_qs
        .filter(delay_rate__gt=WARNING_THRESHOLD)
        .values(
            'id', 'full_name', 'email',
            'delay_rate', 'completion_rate',
            dept_name=F('department__name'),
        )[:10]
    )

    # ── Top Performers ────────────────────────────────────────
    top_performers = list(
        employees_qs
        .filter(total_sub__gt=0)
        .values(
            'id', 'full_name',
            'completion_rate', 'delay_rate', 'performance_score',
            dept_name=F('department__name'),
        )[:5]
    )

    # ── Latest Main Tasks ─────────────────────────────────────
    latest_tasks = list(
        MainTask.objects.select_related('assigned_to', 'department')
        .order_by('-created_at')
        .values(
            'id', 'title', 'priority', 'status', 'due_date',
            dept_name=F('department__name'),
            head_name=F('assigned_to__full_name'),
        )[:6]
    )

    result = {
        'kpi': {
            'total_active_tasks': active,
            'overall_progress'  : overall_progress,
            'dept_efficiency'   : dept_efficiency,
            'critical_delays'   : critical_delays,
        },
        'latest_tasks': latest_tasks,
        'performance_scorecard': {
            'avg_completion_rate': avg_completion,
            'avg_delay_rate'     : avg_delay_emp,
            'quality_score'      : quality_score,
            'total_employees'    : total_employees,
        },
        'warning_list'  : warning_list,
        'top_performers': top_performers,
    }
    
    # Cache the result
    cache.set(cache_key, result, timeout=CACHE_TTL_DASHBOARD)
    return result


# ─── Employee Dashboard ───────────────────────────────────────

def get_employee_dashboard(employee_id, today=None):
    """
    Returns a single dict consumed by EmployeeDashboardSerializer.
    Includes caching per employee.
    """
    if today is None:
        today = timezone.now().date()
    
    cache_key = f"dashboard:employee:{employee_id}:{today}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    month_start = today.replace(day=1)
    subtasks    = SubTask.objects.filter(assigned_to_id=employee_id)

    # ── KPI aggregations — one DB hit ────────────────────────
    agg = subtasks.aggregate(
        assigned_total=Count('id'),
        in_progress=Count('id', filter=Q(status='in_progress')),
        completed_month=Count('id', filter=Q(
            status='completed',
            updated_at__date__gte=month_start,
        )),
    )

    pending_requests = Request.objects.filter(
        employee_id=employee_id,
        status=Request.Status.PENDING,
    ).count()

    # ── Upcoming Deadlines ────────────────────────────────────
    upcoming = list(
        subtasks.select_related('main_task__department')
        .filter(
            due_date__gte=today,
            due_date__lte=today + timedelta(days=7),
        )
        .exclude(status='completed')
        .annotate(
            days_left=ExpressionWrapper(
                F('due_date') - Value(today),
                output_field=FloatField(),
            )
        )
        .order_by('due_date')
        .values(
            'id', 'title', 'due_date', 'status',
            main_task_title=F('main_task__title'),
            dept_name=F('main_task__department__name'),
        )[:5]
    )

    # ── Task Completion Velocity (last 7 days) ────────────────
    velocity = _build_velocity(subtasks, today)

    # ── Priority Mix (DB aggregation) ────────────────────────
    priority_counts = (
        subtasks.exclude(status='completed')
        .values('main_task__priority')
        .annotate(count=Count('id'))
    )

    total_active = sum(r['count'] for r in priority_counts)
    priority_mix = {
        r['main_task__priority']: round(
            (r['count'] / total_active * 100), 1
        ) if total_active > 0 else 0
        for r in priority_counts
    }

    result = {
        'kpi': {
            'assigned_tasks'      : agg['assigned_total'] or 0,
            'in_progress'         : agg['in_progress'] or 0,
            'completed_this_month': agg['completed_month'] or 0,
            'pending_requests'    : pending_requests,
        },
        'upcoming_deadlines': upcoming,
        'velocity'          : velocity,
        'priority_mix'      : priority_mix,
    }
    
    cache.set(cache_key, result, timeout=CACHE_TTL_EMPLOYEE_DASHBOARD)
    return result


def _build_velocity(subtasks_qs, today):
    """
    Returns last 7 days completion counts.
    One DB query using values + annotate grouped by date.
    """
    week_ago = today - timedelta(days=6)

    daily = (
        subtasks_qs
        .filter(
            status='completed',
            updated_at__date__gte=week_ago,
            updated_at__date__lte=today,
        )
        .values('updated_at__date')
        .annotate(completed=Count('id'))
    )

    # Build lookup dict from DB results
    daily_map = {r['updated_at__date']: r['completed'] for r in daily}

    # Fill all 7 days including zeros — minimal Python, just date formatting
    return [
        {
            'day'      : (today - timedelta(days=i)).strftime('%a'),
            'date'     : str(today - timedelta(days=i)),
            'completed': daily_map.get(today - timedelta(days=i), 0),
        }
        for i in range(6, -1, -1)
    ]


# ─── Employee Performance Directory ──────────────────────────

def get_employee_performance(today=None):
    """
    Returns summary + annotated employee list.
    All math done at DB level via custom manager.
    """
    if today is None:
        today = timezone.now().date()
    
    cache_key = f"performance:directory:{today}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    employees_qs = Employee.objects.with_performance_stats(today)

    # Summary aggregations — one DB hit
    agg = employees_qs.aggregate(
        total_staff=Count('id'),
        avg_performance=Avg('completion_rate'),
        avg_delay=Avg('delay_rate'),
        compliant_count=Count(
            'id',
            filter=Q(delay_rate__lt=WARNING_THRESHOLD)
        ),
        critical_delays=Count(
            'id',
            filter=Q(delay_rate__gt=WARNING_THRESHOLD)
        ),
    )

    total_staff   = agg['total_staff'] or 0
    avg_perf      = round(agg['avg_performance'] or 0.0, 1)
    avg_delay     = round(agg['avg_delay'] or 0.0, 1)
    compliant     = agg['compliant_count'] or 0
    compliance    = round((compliant / total_staff * 100), 1) if total_staff > 0 else 0.0

    # Employee list — already annotated, just extract values
    employees = list(
        employees_qs.values(
            'id', 'full_name', 'email', 'status',
            'total_sub', 'completion_rate',
            'delay_rate', 'performance_score',
            dept_name=F('department__name'),
        )
    )

    # Add performance_label — minimal Python, just a lookup
    label_map = lambda score: (
        'On Target' if score >= 80 else
        'Pending'   if score >= 50 else
        'At Risk'
    )
    for emp in employees:
        emp['performance_label'] = label_map(emp['performance_score'] or 0)

    result = {
        'summary': {
            'total_staff'     : total_staff,
            'avg_performance' : avg_perf,
            'avg_delay_rate'  : avg_delay,
            'compliance_rate' : compliance,
            'critical_delays' : agg['critical_delays'] or 0,
        },
        'employees': employees,
    }
    
    cache.set(cache_key, result, timeout=CACHE_TTL_DASHBOARD)
    return result


def get_department_workload(user, today=None):
    """
    FR-DH-06: Department Head Workload View.
    Returns active subtasks count per employee in the DH's department.
    """
    if today is None:
        today = timezone.now().date()
    
    if not user.department:
        return []

    # Import here to avoid circular imports at module level
    from apps.accounts.models import Employee
    
    active_statuses = ['not_started', 'in_progress', 'awaiting_review']
    
    workload = (
        Employee.objects.filter(
            department=user.department,
            status='active'
        )
        .annotate(
            active_subtasks_count=Count(
                'assigned_subtasks',
                filter=Q(
                    assigned_subtasks__status__in=active_statuses,
                    assigned_subtasks__due_date__gte=today
                ),
                distinct=True
            ),
            # Additional metrics for context
            overdue_subtasks_count=Count(
                'assigned_subtasks',
                filter=Q(
                    assigned_subtasks__due_date__lt=today,
                    assigned_subtasks__status__in=active_statuses
                ),
                distinct=True
            )
        )
        .values(
            'id', 
            'full_name', 
            'email',
            'active_subtasks_count',
            'overdue_subtasks_count'
        )
        .order_by('-active_subtasks_count')
    )
    
    return list(workload)