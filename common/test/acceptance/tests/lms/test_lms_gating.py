# -*- coding: utf-8 -*-
"""
End-to-end tests for the gating feature.
"""
from textwrap import dedent

from ..helpers import UniqueCourseTest
from ...pages.studio.auto_auth import AutoAuthPage
from ...pages.studio.overview import CourseOutlinePage
from ...pages.lms.courseware import CoursewarePage
from ...pages.lms.problem import ProblemPage
from ...pages.lms.staff_view import StaffPage
from ...pages.common.logout import LogoutPage
from ...fixtures.course import CourseFixture, XBlockFixtureDesc


class GatingTest(UniqueCourseTest):
    """
    Test gating feature in LMS.
    """
    STAFF_USERNAME = "STAFF_TESTER"
    STAFF_EMAIL = "staff101@example.com"

    STUDENT_USERNAME = "STUDENT_TESTER"
    STUDENT_EMAIL = "student101@example.com"

    def setUp(self):
        super(GatingTest, self).setUp()

        self.logout_page = LogoutPage(self.browser)
        self.courseware_page = CoursewarePage(self.browser, self.course_id)
        self.course_outline = CourseOutlinePage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )

        xml = dedent("""
        <problem>
        <p>What is height of eiffel tower without the antenna?.</p>
        <multiplechoiceresponse>
          <choicegroup label="What is height of eiffel tower without the antenna?" type="MultipleChoice">
            <choice correct="false">324 meters<choicehint>Antenna is 24 meters high</choicehint></choice>
            <choice correct="true">300 meters</choice>
            <choice correct="false">224 meters</choice>
            <choice correct="false">400 meters</choice>
          </choicegroup>
        </multiplechoiceresponse>
        </problem>
        """)
        self.problem1 = XBlockFixtureDesc('problem', 'HEIGHT OF EIFFEL TOWER', data=xml)

        # Install a course with sections/problems
        course_fixture = CourseFixture(
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run'],
            self.course_info['display_name']
        )
        course_fixture.add_advanced_settings({
            "enable_subsection_gating": {"value": "true"}
        })

        course_fixture.add_children(
            XBlockFixtureDesc('chapter', 'Test Section 1').add_children(
                XBlockFixtureDesc('sequential', 'Test Subsection 1').add_children(
                    self.problem1
                ),
                XBlockFixtureDesc('sequential', 'Test Subsection 2').add_children(
                    XBlockFixtureDesc('problem', 'Test Problem 2')
                )
            )
        ).install()

    def _auto_auth(self, username, email, staff):
        """
        Logout and login with given credentials.
        """
        self.logout_page.visit()
        AutoAuthPage(self.browser, username=username, email=email,
                     course_id=self.course_id, staff=staff).visit()

    def _setup_prereq(self):
        """
        Make the first subsection a prerequisite
        """
        # Login as staff
        self._auto_auth(self.STAFF_USERNAME, self.STAFF_EMAIL, True)

        # Make the first subsection a prerequisite
        self.course_outline.visit()
        self.course_outline.open_subsection_settings_dialog(0)
        self.course_outline.select_access_tab()
        self.course_outline.make_gating_prerequisite()

    def _setup_gated_subsection(self):
        """
        Gate the second subsection on the first subsection
        """
        # Login as staff
        self._auto_auth(self.STAFF_USERNAME, self.STAFF_EMAIL, True)

        # Gate the second subsection based on the score achieved in the first subsection
        self.course_outline.visit()
        self.course_outline.open_subsection_settings_dialog(1)
        self.course_outline.select_access_tab()
        self.course_outline.add_prerequisite_to_subsection("80")

    def _fulfill_prereqruisite(self):
        """
        Fulfill the prerequisite needed to see gated content
        """
        problem_page = ProblemPage(self.browser)
        self.assertEqual(problem_page.wait_for_page().problem_name, 'HEIGHT OF EIFFEL TOWER')
        problem_page.click_choice('choice_1')
        problem_page.click_check()

    def test_subsection_gating_in_studio(self):
        """
        Given that I am a staff member
        When I visit the course outline page in studio.
        And open the subsection edit dialog
        Then I can view all settings related to Gating
        And update those settings to gate a subsection
        """
        self._setup_prereq()

        # Assert settings are displayed correctly for a prerequisite subsection
        self.course_outline.visit()
        self.course_outline.open_subsection_settings_dialog(0)
        self.course_outline.select_access_tab()
        self.assertTrue(self.course_outline.gating_prerequisite_checkbox_is_visible())
        self.assertTrue(self.course_outline.gating_prerequisite_checkbox_is_checked())
        self.assertFalse(self.course_outline.gating_prerequisites_dropdown_is_visible())
        self.assertFalse(self.course_outline.gating_prerequisite_min_score_is_visible())

        self._setup_gated_subsection()

        # Assert settings are displayed correctly for a gated subsection
        self.course_outline.visit()
        self.course_outline.open_subsection_settings_dialog(1)
        self.course_outline.select_access_tab()
        self.assertTrue(self.course_outline.gating_prerequisite_checkbox_is_visible())
        self.assertTrue(self.course_outline.gating_prerequisites_dropdown_is_visible())
        self.assertTrue(self.course_outline.gating_prerequisite_min_score_is_visible())

    def test_gated_subsection_in_lms_for_student(self):
        """
        Given that I am a student
        When I visit the LMS Courseware
        Then I cannot see a gated subsection
        When I fulfill the gating Prerequisite
        Then I can see the gated subsection
        """
        self._setup_prereq()
        self._setup_gated_subsection()

        self._auto_auth(self.STUDENT_USERNAME, self.STUDENT_EMAIL, False)

        self.courseware_page.visit()
        self.assertEqual(self.courseware_page.num_subsections, 1)

        # Fulfill prerequisite and verify that gated subsection is shown
        self._fulfill_prereqruisite()
        self.courseware_page.visit()
        self.assertEqual(self.courseware_page.num_subsections, 2)

    def test_gated_subsection_in_lms_for_staff(self):
        """
        Given that I am a staff member
        When I visit the LMS Courseware
        Then I can see all gated subsections
        Displayed along with notification banners
        Then if I masquerade as a student
        Then I cannot see a gated subsection
        When I fufill the gating prerequisite
        Then I can see the gated subsection (without a banner)
        """
        self._setup_prereq()
        self._setup_gated_subsection()

        # Fulfill prerequisites for specific student
        self._auto_auth(self.STUDENT_USERNAME, self.STUDENT_EMAIL, False)
        self.courseware_page.visit()
        self._fulfill_prereqruisite()

        self._auto_auth(self.STAFF_USERNAME, self.STAFF_EMAIL, True)

        banner_message = 'This subsection is unlocked for learners when they meet the pre-requisite requirements.'

        self.courseware_page.visit()
        staff_page = StaffPage(self.browser, self.course_id)
        self.assertEqual(staff_page.staff_view_mode, 'Staff')
        self.assertEqual(self.courseware_page.num_subsections, 2)
        self.assertIn(
            banner_message,
            self.courseware_page.xblock_component_html_content()
        )

        staff_page.set_staff_view_mode('Student')

        self.assertEqual(self.courseware_page.num_subsections, 1)
        self.assertNotIn(
            banner_message,
            self.courseware_page.xblock_component_html_content()
        )

        staff_page.set_staff_view_mode_specific_student(self.STUDENT_USERNAME)

        self.assertEqual(self.courseware_page.num_subsections, 2)
        self.assertNotIn(
            banner_message,
            self.courseware_page.xblock_component_html_content()
        )
