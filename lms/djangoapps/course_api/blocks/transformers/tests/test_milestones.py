"""
Tests for ProctoredExamTransformer.
"""
from mock import patch
from nose.plugins.attrib import attr

import ddt
from edx_proctoring.api import (
    create_exam,
    create_exam_attempt,
    update_attempt_status
)
from edx_proctoring.models import ProctoredExamStudentAttemptStatus
from edx_proctoring.runtime import set_runtime_service
from edx_proctoring.tests.test_services import MockCreditService
from lms.djangoapps.course_blocks.transformers.tests.helpers import CourseStructureTestCase
from student.tests.factories import CourseEnrollmentFactory

from ..milestones import MilestonesTransformer
from ...api import get_course_blocks
from openedx.core.lib.gating import api as gating_api
from milestones.tests.utils import MilestonesTestCaseMixin
from student.roles import (
    CourseStaffRole,
    OrgStaffRole,
    CourseInstructorRole,
    OrgInstructorRole
)


@attr('shard_3')
@ddt.ddt
@patch.dict('django.conf.settings.FEATURES', {'ENABLE_SPECIAL_EXAMS': True, 'MILESTONES_APP': True})
class MilestonesTransformerTestCase(CourseStructureTestCase, MilestonesTestCaseMixin):
    """
    Test behavior of ProctoredExamTransformer
    """
    TRANSFORMER_CLASS_TO_TEST = MilestonesTransformer

    def setUp(self):
        """
        Setup course structure and create user for split test transformer test.
        """
        super(MilestonesTransformerTestCase, self).setUp()

        # Set up proctored exam

        # Build course.
        self.course_hierarchy = self.get_course_hierarchy()
        self.blocks = self.build_course(self.course_hierarchy)
        self.course = self.blocks['course']

        # Enroll user in course.
        CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id, is_active=True)

    def setup_proctored_exam(self, block, attempt_status, user_id):
        """
        Test helper to configure the given block as a proctored exam.
        """
        exam_id = create_exam(
            course_id=unicode(block.location.course_key),
            content_id=unicode(block.location),
            exam_name='foo',
            time_limit_mins=10,
            is_proctored=True,
            is_practice_exam=block.is_practice_exam,
        )

        set_runtime_service(
            'credit',
            MockCreditService(enrollment_mode='verified')
        )

        create_exam_attempt(exam_id, user_id, taking_as_proctored=True)
        update_attempt_status(exam_id, user_id, attempt_status)

    def setup_gated_section(self, gated_block, gating_block):
        """
        Test helper to create a gating requirement.
        Args:
            gated_block: The block that should be inaccessible until gating_block is completed
            gating_block: The block that must be completed before access is granted
        """
        gating_api.add_prerequisite(self.course.id, unicode(gating_block.location))
        gating_api.set_required_content(self.course.id, gated_block.location, gating_block.location, 100)

    ALL_BLOCKS = ('course', 'A', 'B', 'C', 'TimedExam', 'D', 'E', 'PracticeExam', 'F', 'G', 'NotASpecialExam', 'H')

    def get_course_hierarchy(self):
        """
        Get a course hierarchy to test with.
        """

        #                    course
        #               /    |    \
        #              /     |     \
        #            A     Exam1   Exam2
        #          /  \     / \      / \
        #         /   \    /   \    /   \
        #        B    C   D     E  F    G
        #
        return [
            {
                'org': 'MilestonesTransformer',
                'course': 'PE101F',
                'run': 'test_run',
                '#type': 'course',
                '#ref': 'course',
            },
            {
                '#type': 'sequential',
                '#ref': 'A',
                '#children': [
                    {'#type': 'vertical', '#ref': 'B'},
                    {'#type': 'vertical', '#ref': 'C'},
                ],
            },
            {
                '#type': 'sequential',
                '#ref': 'TimedExam',
                'is_time_limited': True,
                'is_proctored_enabled': True,
                'is_practice_exam': False,
                '#children': [
                    {'#type': 'vertical', '#ref': 'D'},
                    {'#type': 'vertical', '#ref': 'E'},
                ],
            },
            {
                '#type': 'sequential',
                '#ref': 'PracticeExam',
                'is_time_limited': True,
                'is_proctored_enabled': True,
                'is_practice_exam': True,
                '#children': [
                    {'#type': 'vertical', '#ref': 'F'},
                    {'#type': 'vertical', '#ref': 'G'},
                ],
            },
            {
                '#type': 'sequential',
                '#ref': 'NotASpecialExam',
                '#children': [
                    {'#type': 'vertical', '#ref': 'H'},
                ],
            },
        ]

    def test_exam_not_created(self):
        block_structure = get_course_blocks(
            self.user,
            self.course.location,
            self.transformers,
        )
        self.assertEqual(
            set(block_structure.get_block_keys()),
            set(self.get_block_key_set(self.blocks, *self.ALL_BLOCKS)),
        )

    @ddt.data(
        (
            'TimedExam',
            ProctoredExamStudentAttemptStatus.declined,
            ALL_BLOCKS,
        ),
        (
            'TimedExam',
            ProctoredExamStudentAttemptStatus.submitted,
            ('course', 'A', 'B', 'C', 'PracticeExam', 'F', 'G', 'NotASpecialExam', 'H'),
        ),
        (
            'TimedExam',
            ProctoredExamStudentAttemptStatus.rejected,
            ('course', 'A', 'B', 'C', 'PracticeExam', 'F', 'G', 'NotASpecialExam', 'H'),
        ),
        (
            'PracticeExam',
            ProctoredExamStudentAttemptStatus.declined,
            ALL_BLOCKS,
        ),
        (
            'PracticeExam',
            ProctoredExamStudentAttemptStatus.rejected,
            ('course', 'A', 'B', 'C', 'TimedExam', 'D', 'E', 'NotASpecialExam', 'H'),
        ),
    )
    @ddt.unpack
    def test_exam_created(self, exam_ref, attempt_status, expected_blocks):
        self.setup_proctored_exam(self.blocks[exam_ref], attempt_status, self.user.id)
        block_structure = get_course_blocks(
            self.user,
            self.course.location,
            self.transformers,
        )
        self.assertEqual(
            set(block_structure.get_block_keys()),
            set(self.get_block_key_set(self.blocks, *expected_blocks)),
        )

    def test_special_exam_gated(self):
        expected_blocks = ('course', 'A', 'B', 'C', 'TimedExam', 'D', 'E', 'NotASpecialExam', 'H')
        self.setup_gated_section(self.blocks['PracticeExam'], self.blocks['TimedExam'])
        block_structure = get_course_blocks(
            self.user,
            self.course.location,
            self.transformers,
        )
        self.assertEqual(
            set(block_structure.get_block_keys()),
            set(self.get_block_key_set(self.blocks, *expected_blocks)),
        )

    def test_not_special_exam_gated(self):
        expected_blocks = ('course', 'A', 'B', 'C', 'TimedExam', 'D', 'E', 'PracticeExam', 'F', 'G')
        self.setup_gated_section(self.blocks['NotASpecialExam'], self.blocks['TimedExam'])
        block_structure = get_course_blocks(
            self.user,
            self.course.location,
            self.transformers,
        )
        self.assertEqual(
            set(block_structure.get_block_keys()),
            set(self.get_block_key_set(self.blocks, *expected_blocks)),
        )

    @ddt.data(CourseStaffRole, OrgStaffRole, CourseInstructorRole, OrgInstructorRole)
    def test_staff_access_gated(self, user_role):
        expected_blocks = ('course', 'A', 'B', 'C', 'TimedExam', 'D', 'E', 'NotASpecialExam', 'H')
        role = user_role(self.course.id)
        role.add_users(self.user)
        self.setup_gated_section(self.blocks['PracticeExam'], self.blocks['TimedExam'])
        block_structure = get_course_blocks(
            self.user,
            self.course.location,
            self.transformers,
        )
        self.assertEqual(
            set(block_structure.get_block_keys()),
            set(self.get_block_key_set(self.blocks, *expected_blocks)),
        )

    @ddt.data(CourseStaffRole, OrgStaffRole, CourseInstructorRole, OrgInstructorRole)
    def test_staff_access_proctored(self, user_role):
        expected_blocks = ('course', 'A', 'B', 'C', 'PracticeExam', 'F', 'G', 'NotASpecialExam', 'H')
        role = user_role(self.course.id)
        role.add_users(self.user)
        self.setup_proctored_exam(self.blocks['TimedExam'], ProctoredExamStudentAttemptStatus.rejected, self.user.id)
        block_structure = get_course_blocks(
            self.user,
            self.course.location,
            self.transformers,
        )
        self.assertEqual(
            set(block_structure.get_block_keys()),
            set(self.get_block_key_set(self.blocks, *expected_blocks)),
        )
