import six
import re

from django.core import mail
from django.core.management import call_command, CommandError
from django.test import TestCase, RequestFactory
from tempfile import NamedTemporaryFile

from testfixtures import LogCapture
from student.tests.factories import UserFactory


LOGGER_NAME = 'student.management.commands.recover_account'


class RecoverAccountTests(TestCase):
    """Test recover account command works fine for all test cases."""

    request_factory = RequestFactory()

    def setUp(self):
        super(RecoverAccountTests, self).setUp()
        self.user = UserFactory.create(username='amy', email='amy@edx.com', password='password')

    def _write_test_csv(self, csv, lines):
        """Write a test csv file with the lines provided"""
        csv.write(b"username,email,new_email\n")
        for line in lines:
            csv.write(six.b(line))
        csv.seek(0)
        return csv

    def test_account_recovery(self):
        """
        test account is recovered. Send email to learner and then reset password. After
        reset password login to make sure account is recovered
        :return:
        """

        with NamedTemporaryFile() as csv:
            csv = self._write_test_csv(csv, lines=['amy,amy@edx.com,amy@newemail.com\n'])
            call_command("recover_account", "--csv_file_path={}".format(csv.name))

            self.assertEqual(len(mail.outbox), 1)

        reset_link = re.findall("(http.+pwreset)", mail.outbox[0].body)[0]
        request_params = {'new_password1': 'password1', 'new_password2': 'password1'}
        self.client.get(reset_link)
        resp = self.client.post(reset_link, data=request_params)

        # Verify the response status code is: 302 with password reset because 302 means success
        self.assertEqual(resp.status_code, 302)

        self.assertTrue(self.client.login(username=self.user.username, password='password1'))

        # try to login with previous password
        self.assertFalse(self.client.login(username=self.user.username, password='password'))

    def test_file_not_found_error(self):
        """
        test command error raised when csv path is invalid
        :return:
        """
        with self.assertRaises(CommandError):
            call_command("recover_account", "--csv_file_path={}".format('test'))

    def test_exception_raised(self):
        """
        test exception raised
        :return:
        """
        with NamedTemporaryFile() as csv:
            csv = self._write_test_csv(csv, lines=['amm,amy@myedx.com,amy@newemail.com\n'])

            expected_message = 'Unable to send email to amy@myedx.com and ' \
                               'exception was User matching query does not exist.'

            with LogCapture(LOGGER_NAME) as log:
                call_command("recover_account", "--csv_file_path={}".format(csv.name))

                log.check_present(
                    (LOGGER_NAME, 'ERROR', expected_message)
                )

    def test_successfull_users_logged(self):
        with NamedTemporaryFile() as csv:
            csv = self._write_test_csv(csv, lines=['amy,amy@edx.com,amy@newemail.com\n'])

            expected_message = "Successfully updated ['amy@newemail.com'] accounts. Failed to update [] accounts"

            with LogCapture(LOGGER_NAME) as log:
                call_command("recover_account", "--csv_file_path={}".format(csv.name))

                log.check_present(
                    (LOGGER_NAME, 'INFO', expected_message)
                )
