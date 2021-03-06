from django.test import TestCase

from iati.factory.iati_factory import (
    ActivityFactory, OrganisationFactory, ReportingOrganisationFactory
)
from iati.models import ActivityReportingOrganisation
from iati_codelists.factory.codelist_factory import VersionFactory
from iati_organisation.parser import post_save
from iati_organisation.parser.organisation_2_01 import Parse as Org_Parser_201


class PostSaveOrganisationTestCase(TestCase):
    """
    2.01: post organisation actions called
    """

    def setUp(self):
        self.parser = Org_Parser_201(None)
        self.version = VersionFactory.create(code='2.01')
        self.organisation = OrganisationFactory.create(
            organisation_identifier='org1',
            iati_standard_version=self.version)

    def test_set_activity_reporting_organisation(self):
        """
        test update ActivityParticipatingOrganisation.organisation references
        to this organisation
        """

        # create ActivityReportingOrganisation with ref this org,
        # organisation=None

        activity = ActivityFactory.create(
            iati_identifier='IATI-0001',
            iati_standard_version=self.version)

        ReportingOrganisationFactory.create(
            activity=activity,
            ref="org1",
            organisation=None
        )

        # check if references are set after calling
        # set_activity_reporting_organisation
        post_save.set_activity_reporting_organisation(self.organisation)

        aro = ActivityReportingOrganisation.objects.all()[0]
        self.assertEqual(aro.organisation.id, self.organisation.id)
