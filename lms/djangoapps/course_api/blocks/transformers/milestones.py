"""
Milestones Transformer
"""

from django.conf import settings

from edx_proctoring.api import get_attempt_status_summary
from edx_proctoring.models import ProctoredExamStudentAttemptStatus
from openedx.core.lib.block_structure.transformer import BlockStructureTransformer, FilteringTransformerMixin
from util import milestones_helpers
from courseware.masquerade import is_masquerading_as_student
from courseware.access_utils import in_preview_mode
from student.roles import (
    GlobalStaff,
    CourseStaffRole,
    OrgStaffRole
)


class MilestonesTransformer(FilteringTransformerMixin, BlockStructureTransformer):
    """
    Exclude proctored exams unless the user is not a verified student or has
    declined taking the exam.
    """
    VERSION = 1
    BLOCK_HAS_PROCTORED_EXAM = 'has_proctored_exam'

    @classmethod
    def name(cls):
        return "milestones"

    @classmethod
    def collect(cls, block_structure):
        """
        Computes any information for each XBlock that's necessary to execute
        this transformer's transform method.

        Arguments:
            block_structure (BlockStructureCollectedData)
        """
        block_structure.request_xblock_fields('is_proctored_enabled')
        block_structure.request_xblock_fields('is_practice_exam')

    def transform_block_filters(self, usage_info, block_structure):
        def user_gated_from_block(block_key):
            """
            Checks whether the user is gated from accessing this block, first via exam proctoring, then via a general
            milestones check.
            """
            return not self.has_staff_access_to_course(block_key, usage_info.user) and (
                self.is_proctored_exam(block_key, usage_info, block_structure) or
                self.has_pending_milestones_for_user(block_key, usage_info)
            )

        return [block_structure.create_removal_filter(user_gated_from_block)]

    @staticmethod
    def is_proctored_exam(block_key, usage_info, block_structure):
        """
        Test whether the block is a special exam for the user in
        question.
        """
        if (
                block_key.block_type == 'sequential' and (
                    block_structure.get_xblock_field(block_key, 'is_proctored_enabled') or
                    block_structure.get_xblock_field(block_key, 'is_practice_exam')
                )
        ):
            # This section is an exam.  It should be excluded unless the
            # user is not a verified student or has declined taking the exam.
            user_exam_summary = get_attempt_status_summary(
                usage_info.user.id,
                unicode(block_key.course_key),
                unicode(block_key),
            )
            return settings.FEATURES.get('ENABLE_SPECIAL_EXAMS', False) and user_exam_summary \
                and user_exam_summary['status'] != ProctoredExamStudentAttemptStatus.declined
        else:
            return False

    @staticmethod
    def has_pending_milestones_for_user(block_key, usage_info):
        """
        Test whether the current user has any unfulfilled milestones preventing
        them from accessing this block.
        """
        return bool(milestones_helpers.get_course_content_milestones(
            unicode(block_key.course_key),
            unicode(block_key),
            'requires',
            usage_info.user.id
        ))

    @staticmethod
    def has_staff_access_to_course(course_key, user):
        """
        Tests whether the current user has staff access to the block being passed in.
        """
        if user is None or (not user.is_authenticated()):
            return False

        if not in_preview_mode() and is_masquerading_as_student(user, course_key):
            return False

        return (
            GlobalStaff().has_user(user) or
            CourseStaffRole(course_key).has_user(user) or
            OrgStaffRole(course_key.org).has_user(user)
        )
