from django.test import TestCase

from dimension.models import Dimension, DimensionValue
from dimension.setup import (
    BRANCH_DIMENSION_CODE,
    DEFAULT_FIRST_BRANCH_CODE,
    DEFAULT_FIRST_BRANCH_DESCRIPTION,
    ensure_default_branch_dimension_and_gl_setup,
)


class DefaultBranchSetupTests(TestCase):
    def test_creates_main_branch_and_is_idempotent(self):
        branch_dim = Dimension.objects.filter(code__iexact=BRANCH_DIMENSION_CODE).first()
        if branch_dim:
            DimensionValue.objects.filter(dimension_code=branch_dim).delete()

        result = ensure_default_branch_dimension_and_gl_setup()
        branch_value = result["default_branch_value"]
        self.assertEqual(branch_value.code, DEFAULT_FIRST_BRANCH_CODE)
        self.assertEqual(branch_value.description, DEFAULT_FIRST_BRANCH_DESCRIPTION)

        branch_dim = Dimension.objects.get(code=BRANCH_DIMENSION_CODE)
        count_after_first = DimensionValue.objects.filter(
            dimension_code=branch_dim
        ).count()
        self.assertEqual(count_after_first, 1)

        result2 = ensure_default_branch_dimension_and_gl_setup()
        self.assertEqual(result2["default_branch_value"].pk, branch_value.pk)
        self.assertEqual(
            DimensionValue.objects.filter(dimension_code=branch_dim).count(),
            count_after_first,
        )
