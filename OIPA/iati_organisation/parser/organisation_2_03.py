from django.conf import settings

from geodata.models import Country, Region
from iati.parser.exceptions import (
    FieldValidationError, ParserError, RequiredFieldError
)
from iati.parser.iati_parser import IatiParser
from iati_codelists import models as codelist_models
from iati_organisation.models import (
    DocumentLinkRecipientCountry, DocumentLinkTitle, Organisation,
    OrganisationDocumentLink, OrganisationDocumentLinkCategory,
    OrganisationDocumentLinkDescription, OrganisationDocumentLinkLanguage,
    OrganisationName, OrganisationNarrative, OrganisationReportingOrganisation,
    RecipientCountryBudget, RecipientCountryBudgetLine, RecipientOrgBudget,
    RecipientOrgBudgetLine, RecipientRegionBudget, RecipientRegionBudgetLine,
    TotalBudget, TotalBudgetLine, TotalExpenditure, TotalExpenditureLine
)
from iati_organisation.parser import post_save
from iati_vocabulary.models import RegionVocabulary


class Parse(IatiParser):
    """
    This covers elements as The IATI Organisation File Standard.
    http://reference.iatistandard.org/203/organisation-standard/overview
    /organisation-file/
    """

    organisation_identifier = ''

    def __init__(self, *args, **kwargs):
        super(Parse, self).__init__(*args, **kwargs)
        self.VERSION = '2.03'

        # default currency
        self.default_currency = None

        # We need a current index to put the current model
        # on the process parse
        self.organisation_document_link_current_index = 0
        self.document_link_title_current_index = 0
        self.document_link_language_current_index = 0
        self.total_budget_current_index = 0
        self.total_budget_line_current_index = 0
        self.total_expenditure_current_index = 0
        self.total_expenditure_line_current_index = 0

    def add_narrative(self, element, parent):
        default_lang = self.default_lang  # set on organisation. (if set)
        lang = element.attrib.get('{http://www.w3.org/XML/1998/namespace}lang')
        text = element.text

        language = self.get_or_none(codelist_models.Language, code=lang)

        if not language:
            language = default_lang

        if not parent:
            raise ParserError(
                "Unknown",
                "Narrative",
                "parent object must be passed")

        register_name = parent.__class__.__name__ + "Narrative"

        if not language:
            raise RequiredFieldError(
                register_name,
                "xml:lang",
                "must specify xml:lang on iati-organisation or xml:lang on \
                        the element itself")
        if not text:
            raise RequiredFieldError(
                register_name,
                "text",
                "empty narrative")

        narrative = OrganisationNarrative()
        narrative.language = language
        narrative.content = element.text
        # This (instead of narrative.related_object) is required, otherwise
        # related object doesn't get passed to the model_store (memory) and
        # 'update_related()' fails.
        # It should probably be passed to the __init__() ?
        setattr(narrative, '_related_object', parent)

        narrative.organisation = self.get_model('Organisation')

        # TODO: handle this differently (also: breaks tests)
        self.register_model(register_name, narrative)

    def _get_currency_or_raise(self, model_name, currency):
        """
        get default currency if not available for currency-related fields
        """
        if not currency:
            currency = getattr(self.get_model(
                'Organisation'), 'default_currency')
            if not currency:
                raise RequiredFieldError(
                    model_name,
                    "currency",
                    "must specify default-currency on iati-organisation or \
                        as currency on the element itself")
        return currency

    def iati_organisations__iati_organisation(self, element):
        organisation_identifier = element.xpath('organisation-identifier')
        if len(organisation_identifier) is not 1:
            raise ParserError("Organisation", "organisation-identifier",
                              "must occur once and only once.")
        # Here organisation_identifier is a string.
        organisation_identifier = organisation_identifier[0].text

        if organisation_identifier is None:
            raise RequiredFieldError("Organisation",
                                     "organisation-identifier", "required "
                                                                "field "
                                                                "missing.")
        # Here normalized_organisation_identifier is a string.
        normalized_organisation_identifier = self._normalize(
            organisation_identifier)

        # Although name and reporting-org is saved in different table,
        # according to specifications it must occur once and only once in
        # organisation element. So we check if 'name' and 'reporting-org'
        # element occurs at least once here.
        name = element.xpath("name")
        reporting_org = element.xpath("reporting-org")
        if len(name) and len(reporting_org) is not 1:
            raise ParserError("Organisation", "name and reporting-org",
                              "must occur at least once.")

        last_updated_datetime = self.validate_date(element.attrib.get(
            "last-updated-datetime"))
        default_lang_code = element.attrib.get(
            '{http://www.w3.org/XML/1998/namespace}lang',
            settings.DEFAULT_LANG)
        if default_lang_code:
            default_lang_code = default_lang_code.lower()

        default_lang = self.get_or_none(
            codelist_models.Language,
            code=default_lang_code
        )
        default_currency = self.get_or_none(
            codelist_models.Currency,
            code=element.attrib.get('default-currency'))

        old_organisation = self.get_or_none(
            Organisation, organisation_identifier=organisation_identifier)
        if old_organisation:
            if old_organisation.last_updated_datetime < last_updated_datetime:

                OrganisationName.objects.filter(
                    organisation=old_organisation).delete()
                OrganisationReportingOrganisation.objects.filter(
                    organisation=old_organisation).delete()
                TotalBudget.objects.filter(
                    organisation=old_organisation).delete()
                RecipientOrgBudget.objects.filter(
                    organisation=old_organisation).delete()
                RecipientCountryBudget.objects.filter(
                    organisation=old_organisation).delete()
                RecipientRegionBudget.objects.filter(
                    organisation=old_organisation).delete()
                TotalExpenditure.objects.filter(
                    organisation=old_organisation).delete()
                OrganisationDocumentLink.objects.filter(
                    organisation=old_organisation).delete()

                organisation = old_organisation
                organisation.organisation_identifier = organisation_identifier
                organisation.normalized_organisation_identifier = \
                    normalized_organisation_identifier
                organisation.last_updated_datetime = last_updated_datetime
                organisation.default_lang = default_lang
                organisation.iati_standard_version_id = self.VERSION
                organisation.default_currency = default_currency

                organisation.published = True
                organisation.ready_to_publish = True
                organisation.modified = True

                self.organisation_identifier = \
                    organisation.organisation_identifier
                self.default_currency = default_currency

                # for later reference
                self.default_lang = default_lang

                self.register_model('Organisation', organisation)

                return element
            else:  # if the current element's date is later than or equal to
                # the existing element's date, raise parser error.
                raise ParserError("Organisation",
                                  None, msg="last-updated-datetime "
                                            "is earlier than old element's "
                                            "last_updated_datetime.")
        else:
            organisation = Organisation()

            organisation.organisation_identifier = organisation_identifier
            organisation.normalized_organisation_identifier = \
                normalized_organisation_identifier
            organisation.last_updated_datetime = last_updated_datetime
            organisation.default_lang = default_lang
            organisation.iati_standard_version_id = self.VERSION
            organisation.default_currency = default_currency

            organisation.published = True
            organisation.ready_to_publish = True
            organisation.modified = False

            self.organisation_identifier = organisation.organisation_identifier
            self.default_currency = default_currency

            # for later reference
            self.default_lang = default_lang

            self.register_model('Organisation', organisation)

            return element

    def iati_organisations__iati_organisation__name(self, element):

        # Although OrganisationName and Organisation has One-to-One relation
        # on the database level, we check here whether element 'name' occurs
        # only once in the parent element 'organisation'.
        organisation = self.get_model('Organisation')
        if 'OrganisationName' in self.model_store:
            for name in self.model_store['OrganisationName']:
                if name.organisation == organisation:
                    raise ParserError("Organisation", "OrganisationName",
                                      "must occur no more than once.")
        # narrative is parsed in different method but as it is required
        # sub-element in 'name' element so we check it here.
        narrative = element.xpath("narrative")
        if len(narrative) < 1:
            raise RequiredFieldError("OrganisationName", "narrative",
                                     "must occur at least once.")
        organisation_name = OrganisationName()
        organisation_name.organisation = organisation

        self.register_model("OrganisationName", organisation_name)
        return element

    def iati_organisations__iati_organisation__reporting_org(self, element):
        # Although OrganisationReportingOrganisation and Organisation has
        # One-to-One relation on the database level, we check here whether
        # element 'reporting-org' occurs only once in the parent element
        # 'organisation'.
        organisation = self.get_model('Organisation')
        if 'OrganisationReportingOrganisation' in self.model_store:
            for reporting_org in self.model_store[
                    'OrganisationReportingOrganisation']:
                if reporting_org.organisation == organisation:
                    raise ParserError("Organisation",
                                      "OrganisationReportingOrganisation",
                                      "must occur no more than once.")
        # narrative is parsed in different method but as it is required
        # sub-element in 'name' element so we check it here.
        narrative = element.xpath("narrative")
        if len(narrative) < 1:
            raise RequiredFieldError("OrganisationName", "narrative",
                                     "must occur at least once.")
        reporting_org_identifier = element.attrib.get("ref")
        if reporting_org_identifier is None:
            raise RequiredFieldError("OrganisationReportingOrganisation",
                                     "ref", "required field missing.")
        org_type = element.attrib.get("type")
        if org_type is None:
            raise RequiredFieldError("OrganisationReportingOrganisation",
                                     "type", "required field missing.")
        # here org_type is OrganisationType object.
        org_type = self.get_or_none(codelist_models.OrganisationType,
                                    code=org_type)
        if org_type is None:
            raise FieldValidationError(
                "OrganisationReportingOrganisation",
                "type",
                "not found on the accompanying codelist.",
                None,
                None,
            )
        secondary_reporter = self.makeBool(element.attrib.get(
            "secondary-reporter"))

        reporting_org = OrganisationReportingOrganisation()
        reporting_org.organisation = organisation
        reporting_org.org_type = org_type
        reporting_org.secondary_reporter = secondary_reporter
        reporting_org.reporting_org_identifier = reporting_org_identifier

        self.register_model("OrganisationReportingOrganisation", reporting_org)
        return element

    def iati_organisations__iati_organisation__reporting_org__narrative(
            self, element):
        reporting_org = self.get_model('OrganisationReportingOrganisation')
        self.add_narrative(element, reporting_org)
        return element

    def iati_organisations__iati_organisation__total_budget(self, element):
        status = element.attrib.get("status")
        if status:
            status = self.get_or_none(codelist_models.BudgetStatus,
                                      code=status)
            if status is None:
                raise FieldValidationError(
                    "OrganisationReportingOrganisation",
                    "status",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )
        else:
            status = codelist_models.BudgetStatus.objects.get(code=1)
        period_start = element.xpath("period-start")
        if len(period_start) is not 1:
            raise ParserError("TotalBudget",
                              "period-start",
                              "must occur once and only once.")
        period_start_date = period_start[0].attrib.get("iso-date")
        if period_start_date is None:
            raise RequiredFieldError("TotalBudget", "iso-date", "required "
                                                                "field "
                                                                "missing.")
        period_start_date = self.validate_date(period_start_date)
        if not period_start_date:
            raise FieldValidationError(
                "TotalBudget",
                "iso-date",
                "is not in correct range.",
                None,
                None,
                )

        period_end = element.xpath("period-end")
        if len(period_end) is not 1:
            raise ParserError("TotalBudget",
                              "period-end",
                              "must occur once and only once.")
        period_end_date = period_end[0].attrib.get("iso-date")
        if period_end_date is None:
            raise RequiredFieldError("TotalBudget", "iso-date", "required "
                                                                "field "
                                                                "missing.")
        period_end_date = self.validate_date(period_end_date)
        if not period_end_date:
            raise FieldValidationError(
                "TotalBudget",
                "iso-date",
                "is not in correct range.",
                None,
                None,
            )

        value_element = element.xpath("value")
        if len(value_element) is not 1:
            raise ParserError("TotalBudget",
                              "value",
                              "must occur once and only once.")
        value = self.guess_number("TotalBudget", value_element[0].text)

        currency = value_element[0].attrib.get("currency")
        if not currency:
            currency = getattr(self.get_model("Organisation"),
                               "default_currency")
            if not currency:
                raise RequiredFieldError(
                    "TotalBudget",
                    "currency",
                    "must specify default-currency on iati-activity or as "
                    "currency on the element itself."
                )
        else:
            currency = self.get_or_none(codelist_models.Currency,
                                        code=currency)
            if currency is None:
                raise FieldValidationError(
                    "TotalBudget",
                    "currency",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )
        value_date = value_element[0].attrib.get("value-date")
        if value_date is None:
            raise RequiredFieldError("TotalBudget", "value-date", "required "
                                                                  "field "
                                                                  "missing.")
        value_date = self.validate_date(value_date)
        if not value_date:
            raise FieldValidationError(
                "TotalBudget",
                "value-date",
                "not in the correct range.",
                None,
                None,
            )
        total_budget = TotalBudget()
        organisation = self.get_model("Organisation")
        total_budget.organisation = organisation
        total_budget.status = status
        total_budget.period_start = period_start_date
        total_budget.period_end = period_end_date
        total_budget.value = value
        total_budget.currency = currency
        total_budget.value_date = value_date
        self.register_model("TotalBudget", total_budget)
        return element

    def iati_organisations__iati_organisation__total_budget__budget_line(
            self, element):
        ref = element.attrib.get("ref")
        narrative = element.xpath("narrative")
        # "narrative" element must occur at least once.
        if len(narrative) < 1:
            raise ParserError("TotalBudgetLine", "narrative", "must occur at "
                                                              "least once.")
        value_element = element.xpath("value")
        # "value"element must occur once and only once.
        if len(value_element) is not 1:
            raise ParserError("TotalBudgetLine",
                              "value",
                              "must occur once and only once.")
        value = self.guess_number("TotalBudget", value_element[0].text)
        currency = value_element[0].attrib.get("currency")
        if not currency:
            currency = getattr(self.get_model("Organisation"),
                               "default_currency")
            if not currency:
                raise RequiredFieldError(
                    "TotalBudgetLine",
                    "currency",
                    "must specify default-currency on iati-activity or as "
                    "currency on the element itself."
                )

        else:
            currency = self.get_or_none(codelist_models.Currency,
                                        code=currency)
            if currency is None:
                raise FieldValidationError(
                    "TotalBudgetLine",
                    "currency",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )
        value_date = value_element[0].attrib.get("value-date")
        if value_date is None:
            raise RequiredFieldError("TotalBudget", "value-date", "required "
                                                                  "field "
                                                                  "missing.")
        value_date = self.validate_date(value_date)
        if not value_date:
            raise FieldValidationError(
                "TotalBudgetLine",
                "value-date",
                "not in the correct range.",
                None,
                None,
            )
        total_budget = self.get_model("TotalBudget")
        total_budtet_line = TotalBudgetLine()

        total_budtet_line.total_budget = total_budget
        total_budtet_line.ref = ref
        total_budtet_line.currency = currency
        total_budtet_line.value = value
        total_budtet_line.value_date = value_date

        self.register_model("TotalBudgetLine", total_budtet_line)
        return element

    def iati_organisations__iati_organisation__total_budget__budget_line__narrative(  # NOQA: E501
            self, element):
        budget_line = self.get_model("TotalBudgetLine")
        self.add_narrative(element, budget_line)
        return element

    def iati_organisations__iati_organisation__recipient_org_budget(self,
                                                                    element):
        status = element.attrib.get("status")
        if status:
            status = self.get_or_none(codelist_models.BudgetStatus,
                                      code=status)
            if status is None:
                raise FieldValidationError(
                    "RecipientOrgBudget",
                    "status",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )
        else:
            status = codelist_models.BudgetStatus.objects.get(code=1)
        recipient_org = element.xpath("recipient-org")
        if len(recipient_org) is not 1:
            raise ParserError("RecipientOrgBudget",
                              "recipient-org",
                              "must occur once and only once.")
        narrative = recipient_org[0].xpath("narrative")
        if len(narrative) < 1:
            raise ParserError("RecipientOrgBudget",
                              "recipient-org",
                              "must occur at least once.")

        recipient_org_budget = RecipientOrgBudget()
        recipient_org_identifier = recipient_org[0].attrib.get("ref")
        if Organisation.objects.filter(
                organisation_identifier=recipient_org_identifier).exists():
            recipient_org = Organisation.objects.get(
                organisation_identifier=recipient_org_identifier)
            recipient_org_budget.recipient_org = recipient_org

        period_start = element.xpath("period-start")
        if len(period_start) is not 1:
            raise ParserError("RecipientOrgBudget",
                              "period-start",
                              "must occur once and only once.")
        period_start_date = period_start[0].attrib.get("iso-date")
        if period_start_date is None:
            raise RequiredFieldError("RecipientOrgBudget", "iso-date",
                                     "required field missing.")
        period_start_date = self.validate_date(period_start_date)
        if not period_start_date:
            raise FieldValidationError(
                "RecipientOrgBudget",
                "iso-date",
                "is not in correct range.",
                None,
                None,
            )
        period_end = element.xpath("period-end")
        if len(period_end) is not 1:
            raise ParserError("RecipientOrgBudget",
                              "period-end",
                              "must occur once and only once.")
        period_end_date = period_end[0].attrib.get("iso-date")
        if period_end_date is None:
            raise RequiredFieldError("RecipientOrgBudget", "iso-date",
                                     "required field missing.")
        period_end_date = self.validate_date(period_end_date)
        if not period_end_date:
            raise FieldValidationError(
                "RecipientOrgBudget",
                "iso-date",
                "is not in correct range.",
                None,
                None,
            )
        value_element = element.xpath("value")
        if len(value_element) is not 1:
            raise ParserError("RecipientOrgBudget",
                              "value",
                              "must occur once and only once.")
        value = self.guess_number("RecipientOrgBudget", value_element[0].text)

        currency = value_element[0].attrib.get("currency")
        if not currency:
            currency = getattr(self.get_model("Organisation"),
                               "default_currency")
            if not currency:
                raise RequiredFieldError(
                    "RecipientOrgBudget",
                    "currency",
                    "must specify default-currency on iati-organisation or "
                    "as currency on the element itself."
                )
        else:
            currency = self.get_or_none(codelist_models.Currency,
                                        code=currency)
            if not currency:
                raise FieldValidationError(
                    "RecipientOrgBudget",
                    "currency",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )

        value_date = value_element[0].attrib.get("value-date")
        if value_date is None:
            raise RequiredFieldError("RecipientOrgBudget", "value-date",
                                     "required field missing.")
        value_date = self.validate_date(value_date)
        if not value_date:
            raise FieldValidationError(
                "RecipientOrgBudget",
                "value-date",
                "not in the correct range.",
                None,
                None,
            )
        organisation = self.get_model("Organisation")

        recipient_org_budget.organisation = organisation
        recipient_org_budget.status = status
        recipient_org_budget.recipient_org_identifier = \
            recipient_org_identifier
        recipient_org_budget.period_start = period_start_date
        recipient_org_budget.period_end = period_end_date
        recipient_org_budget.value_date = value_date
        recipient_org_budget.currency = currency
        recipient_org_budget.value = value

        self.register_model("RecipientOrgBudget", recipient_org_budget)
        return element

    def iati_organisations__iati_organisation__recipient_org_budget__recipient_org__narrative(  # NOQA: E501
            self, element):
        recipient_org_budget = self.get_model('RecipientOrgBudget')
        self.add_narrative(element, recipient_org_budget)
        return element

    def iati_organisations__iati_organisation__recipient_org_budget__budget_line(  # NOQA: E501
            self, element):
        ref = element.attrib.get("ref")
        narrative = element.xpath("narrative")
        # "narrative" element must occur at least once.
        if len(narrative) < 1:
            raise ParserError("RecipientOrgBudgetLine", "narrative",
                              "must occur at least once.")
        value_element = element.xpath("value")
        # "value"element must occur once and only once.
        if len(value_element) is not 1:
            raise ParserError("RecipientOrgBudgetLine",
                              "value",
                              "must occur once and only once.")
        value = self.guess_number("RecipientOrgBudget", value_element[0].text)
        currency = value_element[0].attrib.get("currency")
        if not currency:
            currency = getattr(self.get_model("Organisation"),
                               "default_currency")
            if not currency:
                raise RequiredFieldError(
                    "RecipientOrgBudgetLine",
                    "currency",
                    "must specify default-currency on iati-activity or as "
                    "currency on the element itself."
                )

        else:
            currency = self.get_or_none(codelist_models.Currency,
                                        code=currency)
            if currency is None:
                raise FieldValidationError(
                    "RecipientOrgBudgetLine",
                    "currency",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )
        value_date = value_element[0].attrib.get("value-date")
        if value_date is None:
            raise RequiredFieldError("RecipientOrgBudgetLine",
                                     "value-date",
                                     "required field missing."
                                     )

        value_date = self.validate_date(value_date)
        if not value_date:
            raise FieldValidationError(
                "RecipientOrgBudgetLine",
                "value-date",
                "not in the correct range.",
                None,
                None,
            )
        recipient_org_budget = self.get_model("RecipientOrgBudget")
        recipient_org_budget_line = RecipientOrgBudgetLine()

        recipient_org_budget_line.recipient_org_budget = recipient_org_budget
        recipient_org_budget_line.ref = ref
        recipient_org_budget_line.currency = currency
        recipient_org_budget_line.value = value
        recipient_org_budget_line.value_date = value_date

        self.register_model("RecipientOrgBudgetLine",
                            recipient_org_budget_line)
        return element

    def iati_organisations__iati_organisation__recipient_org_budget__budget_line__narrative(  # NOQA: E501
            self, element):

        recipient_org_budget_line = self.get_model('RecipientOrgBudgetLine')
        self.add_narrative(element, recipient_org_budget_line)
        return element

    def iati_organisations__iati_organisation__recipient_region_budget(
            self, element):
        status = element.attrib.get("status")
        if status:
            status = self.get_or_none(codelist_models.BudgetStatus,
                                      code=status)
            if status is None:
                raise FieldValidationError(
                    "RecipientRegionBudget",
                    "status",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )
        else:
            status = codelist_models.BudgetStatus.objects.get(code=1)
        recipient_region = element.xpath("recipient-region")
        if len(recipient_region) is not 1:
            raise ParserError("RecipientRegionBudget",
                              "recipient-region",
                              "must occur once and only once.")
        narrative = recipient_region[0].xpath("narrative")
        if len(narrative) < 1:
            raise ParserError("RecipientRegionBudget",
                              "recipient-region",
                              "must occur at least once.")

        recipient_region_vocabulary = recipient_region[0].attrib.get(
            "vocabulary")
        if recipient_region_vocabulary:
            recipient_region_vocabulary = self.get_or_none(RegionVocabulary,
                                                           code=recipient_region_vocabulary)  # NOQA: E501
            if recipient_region_vocabulary is None:
                raise FieldValidationError(
                    "RecipientRegionBudget",
                    "vocabulary",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )
        else:
            recipient_region_vocabulary = RegionVocabulary.objects.get(code=1)

        vocabulary_uri = recipient_region[0].attrib.get("vocabulary-uri")
        region = recipient_region[0].attrib.get("code")
        if region and recipient_region_vocabulary == \
                RegionVocabulary.objects.get(code=1):
            region = self.get_or_none(Region, code=region)
            if not region:
                raise FieldValidationError(
                    "RecipientRegionBudget",
                    "region",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )

        period_start = element.xpath("period-start")
        if len(period_start) is not 1:
            raise ParserError("RecipientRegionBudget",
                              "period-start",
                              "must occur once and only once.")
        period_start_date = period_start[0].attrib.get("iso-date")
        if period_start_date is None:
            raise RequiredFieldError("RecipientRegionBudget", "iso-date",
                                     "required field missing.")
        period_start_date = self.validate_date(period_start_date)
        if not period_start_date:
            raise FieldValidationError(
                "RecipientRegionBudget",
                "iso-date",
                "is not in correct range.",
                None,
                None,
            )
        period_end = element.xpath("period-end")
        if len(period_end) is not 1:
            raise ParserError("RecipientRegionBudget",
                              "period-end",
                              "must occur once and only once.")
        period_end_date = period_end[0].attrib.get("iso-date")
        if period_end_date is None:
            raise RequiredFieldError("RecipientRegionBudget", "iso-date",
                                     "required field missing.")
        period_end_date = self.validate_date(period_end_date)
        if not period_end_date:
            raise FieldValidationError(
                "RecipientRegionBudget",
                "iso-date",
                "is not in correct range.",
                None,
                None,
            )
        value_element = element.xpath("value")
        if len(value_element) is not 1:
            raise ParserError("RecipientRegionBudget",
                              "value",
                              "must occur once and only once.")
        value = self.guess_number("RecipientRegionBudget", value_element[
            0].text)

        currency = value_element[0].attrib.get("currency")
        if not currency:
            currency = getattr(self.get_model("Organisation"),
                               "default_currency")
            if not currency:
                raise RequiredFieldError(
                    "RecipientRegionBudget",
                    "currency",
                    "must specify default-currency on iati-organisation or "
                    "as currency on the element itself."
                )
        else:
            currency = self.get_or_none(codelist_models.Currency,
                                        code=currency)
            if not currency:
                raise FieldValidationError(
                    "RecipientRegionBudget",
                    "currency",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )

        value_date = value_element[0].attrib.get("value-date")
        if value_date is None:
            raise RequiredFieldError("RecipientRegionBudget", "value-date",
                                     "required field missing.")
        value_date = self.validate_date(value_date)
        if not value_date:
            raise FieldValidationError(
                "RecipientRegionBudget",
                "value-date",
                "not in the correct range.",
                None,
                None,
            )
        organisation = self.get_model("Organisation")
        recipient_region_budget = RecipientRegionBudget()
        recipient_region_budget.organisation = organisation
        recipient_region_budget.status = status
        recipient_region_budget.region = region
        recipient_region_budget.vocabulary = recipient_region_vocabulary
        recipient_region_budget.vocabulary_uri = vocabulary_uri
        recipient_region_budget.period_start = period_start_date
        recipient_region_budget.period_end = period_end_date
        recipient_region_budget.value_date = value_date
        recipient_region_budget.currency = currency
        recipient_region_budget.value = value

        self.register_model("RecipientRegionBudget", recipient_region_budget)
        return element

    def iati_organistions__iati_organisation__recipient_region_budget__recipient_region__narrative(self, element):  # NOQA: E501
        recipient_region_budget = self.get_model('RecipientRegionBudget')
        self.add_narrative(element, recipient_region_budget)
        return element

    def iati_organisations__iati_organisation__recipient_region_budget__budget_line(  # NOQA: E501
            self, element):
        ref = element.attrib.get("ref")
        narrative = element.xpath("narrative")
        # "narrative" element must occur at least once.
        if len(narrative) < 1:
            raise ParserError("RecipientRegionBudgetLine", "narrative",
                              "must occur at least once.")
        value_element = element.xpath("value")
        # "value"element must occur once and only once.
        if len(value_element) is not 1:
            raise ParserError("RecipientRegionBudgetLine",
                              "value",
                              "must occur once and only once.")
        value = self.guess_number("RecipientRegionBudget", value_element[
            0].text)
        currency = value_element[0].attrib.get("currency")
        if not currency:
            currency = getattr(self.get_model("Organisation"),
                               "default_currency")
            if not currency:
                raise RequiredFieldError(
                    "RecipientRegionBudgetLine",
                    "currency",
                    "must specify default-currency on iati-activity or as "
                    "currency on the element itself."
                )

        else:
            currency = self.get_or_none(codelist_models.Currency,
                                        code=currency)
            if currency is None:
                raise FieldValidationError(
                    "RecipientRegionBudgetLine",
                    "currency",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )
        value_date = value_element[0].attrib.get("value-date")
        if value_date is None:
            raise RequiredFieldError("RecipientRegionBudgetLine",
                                     "value-date",
                                     "required field missing."
                                     )

        value_date = self.validate_date(value_date)
        if not value_date:
            raise FieldValidationError(
                "RecipientRegionBudgetLine",
                "value-date",
                "not in the correct range.",
                None,
                None,
            )
        recipient_region_budget = self.get_model("RecipientRegionBudget")
        recipient_region_budget_line = RecipientRegionBudgetLine()

        recipient_region_budget_line.recipient_region_budget = \
            recipient_region_budget
        recipient_region_budget_line.ref = ref
        recipient_region_budget_line.currency = currency
        recipient_region_budget_line.value = value
        recipient_region_budget_line.value_date = value_date

        self.register_model("RecipientRegionBudgetLine",
                            recipient_region_budget_line)
        return element

    def iati_organisations__iati_organisation__recipient_region_budget__budget_line__narrative(  # NOQA: E501
            self, element):

        recipient_region_budget_line = self.get_model(
            'RecipientRegionBudgetLine')
        self.add_narrative(element, recipient_region_budget_line)
        return element

    def iati_organisations__iati_organisation__recipient_country_budget(
            self, element):
        status = element.attrib.get("status")
        if status:
            status = self.get_or_none(codelist_models.BudgetStatus,
                                      code=status)
            if status is None:
                raise FieldValidationError(
                    "RecipientCountryBudget",
                    "status",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )
        else:
            status = codelist_models.BudgetStatus.objects.get(code=1)
        recipient_country = element.xpath("recipient-country")
        if len(recipient_country) is not 1:
            raise ParserError("RecipientCountryBudget",
                              "recipient-country",
                              "must occur once and only once.")
        narrative = recipient_country[0].xpath("narrative")
        if len(narrative) < 1:
            raise ParserError("RecipientCountryBudget",
                              "recipient-country",
                              "must occur at least once.")

        recipient_country_code = recipient_country[0].attrib.get(
            "code")
        if not recipient_country_code:
            raise RequiredFieldError(
                "RecipientCountryBudget",
                "code",
                "required field missing."
            )
        recipient_country_code = self.get_or_none(Country,
                                                  code=recipient_country_code)
        if not recipient_country_code:
            raise FieldValidationError(
                "RecipientCountryBudget",
                "code",
                "is not in the accompanying codelist.",
                None,
                None,
            )

        period_start = element.xpath("period-start")
        if len(period_start) is not 1:
            raise ParserError("RecipientCountryBudget",
                              "period-start",
                              "must occur once and only once.")
        period_start_date = period_start[0].attrib.get("iso-date")
        if period_start_date is None:
            raise RequiredFieldError("RecipientCountryBudget", "iso-date",
                                     "required field missing.")
        period_start_date = self.validate_date(period_start_date)
        if not period_start_date:
            raise FieldValidationError(
                "RecipientCountryBudget",
                "iso-date",
                "is not in correct range.",
                None,
                None,
            )
        period_end = element.xpath("period-end")
        if len(period_end) is not 1:
            raise ParserError("RecipientCountryBudget",
                              "period-end",
                              "must occur once and only once.")
        period_end_date = period_end[0].attrib.get("iso-date")
        if period_end_date is None:
            raise RequiredFieldError("RecipientCountryBudget", "iso-date",
                                     "required field missing.")
        period_end_date = self.validate_date(period_end_date)
        if not period_end_date:
            raise FieldValidationError(
                "RecipientCountryBudget",
                "iso-date",
                "is not in correct range.",
                None,
                None,
            )
        value_element = element.xpath("value")
        if len(value_element) is not 1:
            raise ParserError("RecipientCountryBudget",
                              "value",
                              "must occur once and only once.")
        value = self.guess_number("RecipientCountryBudget", value_element[
            0].text)

        currency = value_element[0].attrib.get("currency")
        if not currency:
            currency = getattr(self.get_model("Organisation"),
                               "default_currency")
            if not currency:
                raise RequiredFieldError(
                    "RecipientCountryBudget",
                    "currency",
                    "must specify default-currency on iati-organisation or "
                    "as currency on the element itself."
                )
        else:
            currency = self.get_or_none(codelist_models.Currency,
                                        code=currency)
            if not currency:
                raise FieldValidationError(
                    "RecipientCountryBudget",
                    "currency",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )

        value_date = value_element[0].attrib.get("value-date")
        if value_date is None:
            raise RequiredFieldError("RecipientCountryBudget", "value-date",
                                     "required field missing.")
        value_date = self.validate_date(value_date)
        if not value_date:
            raise FieldValidationError(
                "RecipientCountryBudget",
                "value-date",
                "not in the correct range.",
                None,
                None,
            )
        organisation = self.get_model("Organisation")
        recipient_country_budget = RecipientCountryBudget()
        recipient_country_budget.organisation = organisation
        recipient_country_budget.status = status
        recipient_country_budget.country = recipient_country_code
        recipient_country_budget.period_start = period_start_date
        recipient_country_budget.period_end = period_end_date
        recipient_country_budget.value_date = value_date
        recipient_country_budget.currency = currency
        recipient_country_budget.value = value

        self.register_model("RecipientCountryBudget", recipient_country_budget)
        return element

    def iati_organistions__iati_organisation__recipient_country_budget__recipient_country__narrative(  # NOQA: E501
            self, element):
        recipient_country_budget = self.get_model('RecipientCountryBudget')
        self.add_narrative(element, recipient_country_budget)
        return element

    def iati_organisations__iati_organisation__recipient_country_budget__budget_line(self, element):  # NOQA: E501
        ref = element.attrib.get("ref")
        narrative = element.xpath("narrative")
        # "narrative" element must occur at least once.
        if len(narrative) < 1:
            raise ParserError("RecipientCountryBudgetLine", "narrative",
                              "must occur at least once.")
        value_element = element.xpath("value")
        # "value"element must occur once and only once.
        if len(value_element) is not 1:
            raise ParserError("RecipientCountryBudgetLine",
                              "value",
                              "must occur once and only once.")
        value = self.guess_number("RecipientRegionBudget", value_element[
            0].text)
        currency = value_element[0].attrib.get("currency")
        if not currency:
            currency = getattr(self.get_model("Organisation"),
                               "default_currency")
            if not currency:
                raise RequiredFieldError(
                    "RecipientCountryBudgetLine",
                    "currency",
                    "must specify default-currency on iati-activity or as "
                    "currency on the element itself."
                )

        else:
            currency = self.get_or_none(codelist_models.Currency,
                                        code=currency)
            if currency is None:
                raise FieldValidationError(
                    "RecipientCountryBudgetLine",
                    "currency",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )
        value_date = value_element[0].attrib.get("value-date")
        if value_date is None:
            raise RequiredFieldError("RecipientCountryBudgetLine",
                                     "value-date",
                                     "required field missing."
                                     )

        value_date = self.validate_date(value_date)
        if not value_date:
            raise FieldValidationError(
                "RecipientCountryBudgetLine",
                "value-date",
                "not in the correct range.",
                None,
                None,
            )
        recipient_country_budget = self.get_model("RecipientCountryBudget")
        recipient_country_budget_line = RecipientCountryBudgetLine()

        recipient_country_budget_line.recipient_country_budget = \
            recipient_country_budget
        recipient_country_budget_line.ref = ref
        recipient_country_budget_line.currency = currency
        recipient_country_budget_line.value = value
        recipient_country_budget_line.value_date = value_date

        self.register_model("RecipientCountryBudgetLine",
                            recipient_country_budget_line)
        return element

    def iati_organisations__iati_organisation__recipient_country_budget__budget_line__narrative(  # NOQA: E501
            self, element):

        recipient_country_budget_line = self.get_model(
            'RecipientCountryBudgetLine')
        self.add_narrative(element, recipient_country_budget_line)
        return element

    def iati_organisations__iati_organisation__total_expenditure(self,
                                                                 element):
        period_start = element.xpath("period-start")
        if len(period_start) is not 1:
            raise ParserError("TotalExpenditure",
                              "period-start",
                              "must occur once and only once.")
        period_start_date = period_start[0].attrib.get("iso-date")
        if period_start_date is None:
            raise RequiredFieldError("TotalExpenditure", "iso-date",
                                     "required field missing.")
        period_start_date = self.validate_date(period_start_date)
        if not period_start_date:
            raise FieldValidationError(
                "TotalExpenditure",
                "iso-date",
                "is not in correct range.",
                None,
                None,
                )

        period_end = element.xpath("period-end")
        if len(period_end) is not 1:
            raise ParserError("TotalExpenditure",
                              "period-end",
                              "must occur once and only once.")
        period_end_date = period_end[0].attrib.get("iso-date")
        if period_end_date is None:
            raise RequiredFieldError("TotalExpenditure", "iso-date",
                                     "required field missing.")
        period_end_date = self.validate_date(period_end_date)
        if not period_end_date:
            raise FieldValidationError(
                "TotalExpenditure",
                "iso-date",
                "is not in correct range.",
                None,
                None,
            )

        value_element = element.xpath("value")
        if len(value_element) is not 1:
            raise ParserError("TotalExpenditure",
                              "value",
                              "must occur once and only once.")
        value = self.guess_number("TotalExpenditure", value_element[0].text)

        currency = value_element[0].attrib.get("currency")
        if not currency:
            currency = getattr(self.get_model("Organisation"),
                               "default_currency")
            if not currency:
                raise RequiredFieldError(
                    "TotalExpenditure",
                    "currency",
                    "must specify default-currency on iati-activity or as "
                    "currency on the element itself."
                )
        else:
            currency = self.get_or_none(codelist_models.Currency,
                                        code=currency)
            if currency is None:
                raise FieldValidationError(
                    "TotalExpenditure",
                    "currency",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )
        value_date = value_element[0].attrib.get("value-date")
        if value_date is None:
            raise RequiredFieldError("TotalExpenditure",
                                     "value-date",
                                     "required field missing.")
        value_date = self.validate_date(value_date)
        if not value_date:
            raise FieldValidationError(
                "TotalExpenditure",
                "value-date",
                "not in the correct range.",
                None,
                None,
            )
        total_expenditure = TotalExpenditure()
        organisation = self.get_model("Organisation")
        total_expenditure.organisation = organisation
        total_expenditure.period_start = period_start_date
        total_expenditure.period_end = period_end_date
        total_expenditure.value = value
        total_expenditure.currency = currency
        total_expenditure.value_date = value_date
        self.register_model("TotalExpenditure", total_expenditure)
        return element

    def iati_organisations__iati_organisation__total_expenditure__expense_line(self, element):  # NOQA: E501

        ref = element.attrib.get("ref")
        narrative = element.xpath("narrative")
        # "narrative" element must occur at least once.
        if len(narrative) < 1:
            raise ParserError("TotalExpenditureLine", "narrative",
                              "must occur at least once.")
        value_element = element.xpath("value")
        # "value"element must occur once and only once.
        if len(value_element) is not 1:
            raise ParserError("TotalExpenditureLine",
                              "value",
                              "must occur once and only once.")
        value = self.guess_number("TotalExpenditureLine", value_element[
            0].text)
        currency = value_element[0].attrib.get("currency")
        if not currency:
            currency = getattr(self.get_model("Organisation"),
                               "default_currency")
            if not currency:
                raise RequiredFieldError(
                    "TotalExpenditureLine",
                    "currency",
                    "must specify default-currency on iati-activity or as "
                    "currency on the element itself."
                )

        else:
            currency = self.get_or_none(codelist_models.Currency,
                                        code=currency)
            if currency is None:
                raise FieldValidationError(
                    "TotalExpenditureLine",
                    "currency",
                    "not found on the accompanying codelist.",
                    None,
                    None,
                )
        value_date = value_element[0].attrib.get("value-date")
        if value_date is None:
            raise RequiredFieldError("TotalExpenditureLine",
                                     "value-date",
                                     "required field missing."
                                     )

        value_date = self.validate_date(value_date)
        if not value_date:
            raise FieldValidationError(
                "TotalExpenditureLine",
                "value-date",
                "not in the correct range.",
                None,
                None,
            )
        total_expenditure = self.get_model("TotalExpenditure")
        total_expenditure_expense_line = TotalExpenditureLine()

        total_expenditure_expense_line.total_expenditure = total_expenditure
        total_expenditure_expense_line.ref = ref
        total_expenditure_expense_line.currency = currency
        total_expenditure_expense_line.value = value
        total_expenditure_expense_line.value_date = value_date

        self.register_model("TotalExpenditureLine",
                            total_expenditure_expense_line)
        return element

    def iati_organisations__iati_organisation__total_expenditure__expense_line__narrative(self, element):  # NOQA: E501

        total_expenditure_line = self.get_model(
            'TotalExpenditureLine')
        self.add_narrative(element, total_expenditure_line)
        return element

    def iati_organisations__iati_organisation__document_link(self, element):

        url = element.attrib.get("url")
        if not url:
            raise RequiredFieldError(
                "OrganisationDocumentLink",
                "url",
                "required field missing."
            )
        file_format = element.attrib.get("format")
        if not file_format:
            raise RequiredFieldError(
                "OrganisationDocumentLink",
                "file_format",
                "required field missing."
            )
        file_format = self.get_or_none(codelist_models.FileFormat,
                                       code=file_format)
        if not file_format:
            raise FieldValidationError(
                "OrganisationDocumentLink",
                "file_format",
                "not found on the accompanying codelist.",
                None,
                None
            )
        title_list = element.xpath("title")
        if len(title_list) is not 1:
            raise ParserError(
                "OrganisationDocumentLink",
                "title",
                "this element must occur once and only once."
            )
        category_list = element.xpath("category")
        if len(category_list) < 1:
            raise ParserError(
                "OrganisationDocumentLink",
                "categories",
                "this element must occur at least once."
            )
        description_list = element.xpath("description")
        if len(description_list) > 1:
            raise ParserError(
                "OrganisationDocumentLink",
                "description",
                "this element must occur no more than once."
            )
        document_date_list = element.xpath("document-date")
        if len(document_date_list) > 1:
            raise ParserError(
                "OrganisationDocumentLink",
                "document-date",
                "this element must occur no more than once."
            )
        iso_date = None
        if len(document_date_list) == 1:
            iso_date = document_date_list[0].attrib.get("iso-date")
            if not iso_date:
                raise RequiredFieldError(
                    "OrganisationDocumentLink",
                    "iso_date",
                    "required field missing."
                )
            iso_date = self.validate_date(iso_date)
            if iso_date is None:
                raise FieldValidationError(
                    "OrganisationDocumentLink",
                    "iso-date",
                    "not in the correct range.",
                    None,
                    None,
                )
        organisation = self.get_model("Organisation")
        document_link = OrganisationDocumentLink()
        document_link.organisation = organisation
        document_link.url = url
        document_link.file_format = file_format
        document_link.iso_date = iso_date
        self.register_model("OrganisationDocumentLink", document_link)
        return element

    def iati_organisations__iati_organisation__document_link__recipient_country(self, element):  # NOQA: E501
        recipient_country_code = element.attrib.get("code")
        if not recipient_country_code:
            raise RequiredFieldError(
                "DocumentLinkRecipientCountry",
                "recipient_country",
                "required field missing."
            )
        recipient_country = self.get_or_none(Country,
                                             code=recipient_country_code)
        if not recipient_country:
            raise FieldValidationError(
                "DocumentLinkRecipientCountry",
                "recipient_country",
                "not found on the accompanying codelist.",
                None,
                None
            )
        document_link = self.get_model("OrganisationDocumentLink")
        document_link_recipient_country = DocumentLinkRecipientCountry()
        document_link_recipient_country.document_link = document_link
        document_link_recipient_country.recipient_country = recipient_country
        self.register_model("DocumentLinkRecipientCountry",
                            document_link_recipient_country)
        return element

    def iati_organisations__iati_organisation__document_link__recipient_country__narrative(self, element):  # NOQA: E501
        recipient_country = self.get_model(
            'DocumentLinkRecipientCountry')
        self.add_narrative(element, recipient_country)
        return element

    def iati_organisations__iati_organisation__document_link__title(self,
                                                                    element):
        document_link = self.get_model("OrganisationDocumentLink")
        document_link_title = DocumentLinkTitle()
        document_link_title.document_link = document_link
        self.register_model("DocumentLinkTitle", document_link_title)
        return element

    def iati_organisations__iati_organisation__document_link__title__narrative(self, element):  # NOQA: E501
        tital = self.get_model(
            'DocumentLinkTitle')
        self.add_narrative(element, tital)
        return element

    def iati_organisations__iati_organisation__document_link__description(self, element):  # NOQA: E501
        document_link = self.get_model("OrganisationDocumentLink")
        description = OrganisationDocumentLinkDescription()
        description.document_link = document_link
        self.register_model("OrganisationDocumentLinkDescription", description)
        return element

    def iati_organisations__iati_organisation__document_link__description__narrative(self, element):  # NOQA: E501
        description = self.get_model(
            'OrganisationDocumentLinkDescription')
        self.add_narrative(element, description)
        return element

    def iati_organisations__iati_organisation__document_link__category(self,
                                                                       element):  # NOQA: E501
        document_category_code = element.attrib.get("code")
        if not document_category_code:
            raise RequiredFieldError(
                "OrganisationDocumentLinkCategory",
                "category",
                "required field missing."
            )
        document_category = self.get_or_none(
            codelist_models.DocumentCategory, code=document_category_code)
        if not document_category_code:
            raise FieldValidationError(
                "OrganisationDocumentLinkCategory",
                "category",
                "not found on the accompanying codelist.",
                None,
                None
            )
        document_link = self.get_model("OrganisationDocumentLink")
        document_link_category = OrganisationDocumentLinkCategory()
        document_link_category.document_link = document_link
        document_link_category.category = document_category
        self.register_model("OrganisationDocumentLinkCategory",
                            document_link_category)
        return element

    def iati_organisations__iati_organisation__document_link__language(self,
                                                                       element):  # NOQA: E501
        language_code = element.attrib.get("code")
        if not language_code:
            raise RequiredFieldError(
                "OrganisationDocumentLinkLanguage",
                "language",
                "required field missing."
            )
        language = self.get_or_none(codelist_models.Language,
                                    code=language_code)
        if not language:
            raise FieldValidationError(
                "OrganisationDocumentLinkLanguage",
                "language",
                "not found on the accompanying codelist.",
                None,
                None,
            )
        document_link = self.get_model("OrganisationDocumentLink")
        document_link_language = OrganisationDocumentLinkLanguage()
        document_link_language.document_link = document_link
        document_link_language.language = language
        self.register_model("OrganisationDocumentLinkLanguage",
                            document_link_language)
        return element

    def post_save_models(self):
        """Perform all actions that need to happen after a single
        organisation's been parsed."""
        organisation = self.get_model('Organisation')

        if not organisation:
            return False

        post_save.set_activity_reporting_organisation(organisation)
        post_save.set_publisher_fk(organisation)

    def post_save_file(self, xml_source):
        pass

    def post_save_validators(self, dataset):
        pass