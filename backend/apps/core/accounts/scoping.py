"""Row-level scoping (rule 8): `Model.objects.for_user(user)` is the only way views build querysets."""
from django.db import models


class ScopedQuerySet(models.QuerySet):
    customer_field = "customer"  # lookup path from the model to the owning User

    def for_user(self, user):
        if not user or not user.is_authenticated:
            return self.none()
        if user.role == "customer":
            return self.filter(**{self.customer_field: user})
        return self  # admin / staff see everything


def scoped_manager(customer_field="customer"):
    qs = type("ScopedQS", (ScopedQuerySet,), {"customer_field": customer_field})
    return qs.as_manager()
