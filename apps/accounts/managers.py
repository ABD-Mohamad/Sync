# apps/accounts/managers.py
from django.db           import models
from django.db.models    import (
    Count, Q, F, FloatField, Value, ExpressionWrapper, Case, When
)
from django.db.models.functions import Cast, Greatest, Round


class EmployeePerformanceManager(models.Manager):
    """
    Custom manager for Employee model.
    Encapsulates all performance-related annotations at the DB level —
    zero Python loops, all math done in SQL.
    """

    def with_performance_stats(self, today):
        return (
            self.filter(status='active')
            .select_related('department')
            .annotate(
                total_sub=Count('assigned_subtasks'),

                completed_sub=Count(
                    'assigned_subtasks',
                    filter=Q(assigned_subtasks__status='completed'),
                ),

                overdue_sub=Count(
                    'assigned_subtasks',
                    filter=Q(
                        assigned_subtasks__due_date__lt=today
                    ) & ~Q(
                        assigned_subtasks__status='completed'
                    ),
                ),

                # completion_rate = (completed / total) * 100
                completion_rate=Case(
                    When(total_sub=0, then=Value(0.0)),
                    default=Round(
                        ExpressionWrapper(
                            Cast('completed_sub', FloatField())
                            / Cast('total_sub', FloatField())
                            * Value(100.0),
                            output_field=FloatField(),
                        ),
                        precision=1,
                    ),
                    output_field=FloatField(),
                ),

                # delay_rate = (overdue / total) * 100
                delay_rate=Case(
                    When(total_sub=0, then=Value(0.0)),
                    default=Round(
                        ExpressionWrapper(
                            Cast('overdue_sub', FloatField())
                            / Cast('total_sub', FloatField())
                            * Value(100.0),
                            output_field=FloatField(),
                        ),
                        precision=1,
                    ),
                    output_field=FloatField(),
                ),

                # performance_score = max(0, completion_rate - delay_rate)
                performance_score=Case(
                    When(total_sub=0, then=Value(0.0)),
                    default=Greatest(
                        Round(
                            ExpressionWrapper(
                                (
                                    Cast('completed_sub', FloatField())
                                    / Cast('total_sub', FloatField())
                                    * Value(100.0)
                                ) - (
                                    Cast('overdue_sub', FloatField())
                                    / Cast('total_sub', FloatField())
                                    * Value(100.0)
                                ),
                                output_field=FloatField(),
                            ),
                            precision=1,
                        ),
                        Value(0.0),
                    ),
                    output_field=FloatField(),
                ),
            )
            .order_by('-performance_score')
        )