from django.contrib import admin
from django import forms
from django.forms.models import BaseInlineFormSet
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils.functional import curry

from nested_inline.admin import NestedModelAdmin, NestedInline

from iati.models import *
from iati.transaction.models import *

from django.utils.html import format_html

class ExtraNestedModelAdmin(NestedModelAdmin):
    def get_inline_instances(self, request, obj=None):
        inline_instances = super(ExtraNestedModelAdmin, self).get_inline_instances(request, obj)
        for inline_instance in inline_instances:
            inline_instance.parent_instance = obj

        return inline_instances


class ExtraNestedInline(NestedInline):
    def get_inline_instances(self, request, obj=None):
        inline_instances = super(ExtraNestedInline, self).get_inline_instances(request, obj)
        for inline_instance in inline_instances:
            inline_instance.parent_instance = self.parent_instance
            inline_instance.direct_parent = obj

        return inline_instances


# TODO: remove django-grappelli-inline dependency by moving these templates to local repo - 2015-12-01
class NestedStackedInline(ExtraNestedInline):
    template = 'admin/edit_inline/stacked.html'
    # template = 'admin/edit_inline/stacked-nested.html'


class NestedTabularInline(ExtraNestedInline):
    template = 'admin/edit_inline/tabular.html'
    # template = 'admin/edit_inline/tabular-nested.html'


# class NarrativeForm(forms.ModelForm):
#     class Meta:
#         model = Narrative
#         fields = ('language', 'content')


class NarrativeInline(GenericTabularInline):

    model = Narrative
    ct_field = "related_content_type"
    ct_fk_field = "related_object_id"
    inlines = []
    fields = ('language', 'content')
    # form = NarrativeForm


    extra = 2

    def get_formset(self, request, obj=None, **kwargs):
        initial = [{'activity': self.parent_instance} for i in range(self.extra)]
        formset = super(NarrativeInline, self).get_formset(request, obj, **kwargs)
        formset.__init__ = curry(formset.__init__, initial=initial)
        return formset


class OrganisationAdmin(admin.ModelAdmin):
    search_fields = ['code', 'name']
    list_display = ['code', 'abbreviation', 'name', 'type', 'total_activities']


class TransactionDescriptionInline(NestedTabularInline):
    model = TransactionDescription
    inlines = [
        NarrativeInline,
    ]

    extra = 0


class TransactionProviderInline(NestedTabularInline):
    model = TransactionProvider
    inlines = [
        NarrativeInline,
    ]
    exclude = ('normalized_ref', 'organisation', 'provider_activity_ref')

    raw_id_fields = ('provider_activity',)

    autocomplete_lookup_fields = {
        'fk': ['provider_activity'],
    }

    extra = 0

    def save_model(self, request, obj, form, change):
        obj.normalized_ref = obj.ref
        if obj.provider_activity:
            obj.provider_activity_ref = obj.provider_activity.id
        return super(TransactionProviderInline, self).save_model(request, obj, form, change)


class TransactionReceiverInline(NestedTabularInline):
    model = TransactionReceiver
    inlines = [
        NarrativeInline,
    ]
    exclude = ('normalized_ref', 'organisation', 'receiver_activity_ref')

    raw_id_fields = ('receiver_activity',)

    autocomplete_lookup_fields = {
        'fk': ['receiver_activity'],
    }

    extra = 0

    def save_model(self, request, obj, form, change):
        obj.normalized_ref = obj.ref
        if obj.receiver_activity:
            obj.receiver_activity_ref = obj.receiver_activity.id
        return super(TransactionReceiverInline, self).save_model(request, obj, form, change)


class ActivityDateInline(NestedTabularInline):
    model = ActivityDate
    extra = 0


class ActivityReportingOrganisationInline(NestedTabularInline):
    model = ActivityReportingOrganisation
    extra = 0


class ActivityParticipatingOrganisationInline(NestedTabularInline):
    model = ActivityParticipatingOrganisation
    inlines = [
        NarrativeInline,
    ]
    extra = 1


# class TransactionInlineFormSet(BaseInlineFormSet):
#     def save_new(self, form, commit=True):
#
#         return form.save(commit=commit)
#
#     def save_existing(self, form, instance, commit=True):
#         return super(TransactionInlineFormSet, self).save_existing(form, instance, commit=commit)


class TransactionInline(NestedTabularInline):
    model = Transaction

    fields = ('edit_transaction',)
    readonly_fields = ('edit_transaction',)
    # formset = TransactionInlineFormSet

    def edit_transaction(self, obj):

        if obj.id:
            return format_html(
                '<a href="/admin/iati/transaction/{}/" onclick="return showAddAnotherPopup(this);">Edit</a>',
                str(obj.id))
        else:
            return format_html(
                'Please save the activity to edit this transaction')

    extra = 0


class ActivityPolicyMarkerInline(NestedTabularInline):
    model = ActivityPolicyMarker
    extra = 0


class ActivityRecipientCountryInline(NestedTabularInline):
    model = ActivityRecipientCountry
    extra = 0

    raw_id_fields = ('country',)

    autocomplete_lookup_fields = {
        'fk': ['country'],
    }


class ActivitySectorInline(NestedTabularInline):
    model = ActivitySector
    extra = 0

    raw_id_fields = ('sector',)

    autocomplete_lookup_fields = {
        'fk': ['sector'],
    }


class ActivityRecipientRegionInline(NestedTabularInline):
    model = ActivityRecipientRegion
    extra = 0


class BudgetInline(NestedTabularInline):
    model = Budget
    exclude = ('value_string',)
    extra = 0


class CategoriesInline(NestedTabularInline):
    model = DocumentLinkCategory


class DocumentLinkInline(NestedStackedInline):
    inlines = [CategoriesInline, ]

    model = DocumentLink
    extra = 0


class ResultInline(NestedTabularInline):
    model = Result
    extra = 0

    fields = ('edit_result',)
    readonly_fields = ('edit_result',)

    def edit_result(self, obj):
         return format_html(
             '<a href="/admin/iati/result/{}/" onclick="return showAddAnotherPopup(this);">Edit</a>',
             str(obj.id))


class LocationInline(NestedTabularInline):
    model = Location
    extra = 0


class RelatedActivityInline(NestedTabularInline):
    model = RelatedActivity
    fk_name='current_activity'
    extra = 0

    raw_id_fields = ('ref_activity',)

    autocomplete_lookup_fields = {
        'fk': ['ref_activity'],
    }


class DescriptionInline(NestedStackedInline):
    model = Description
    extra = 1
    inlines = [NarrativeInline, ]


class TitleInline(NestedStackedInline):
    model = Title
    extra = 0
    inlines = [NarrativeInline, ]

    def save_formset(self, request, form, formset, change):
        """
        Given an inline formset save it to the database.
        """
        formset.save()

        for form in formset.forms:
            if hasattr(form, 'nested_formsets') and form not in formset.deleted_forms:
                for nested_formset in form.nested_formsets:
                    self.save_formset(request, form, nested_formset, change)


class ActivityAdmin(ExtraNestedModelAdmin):
    search_fields = ['id']
    exclude = (
        'activity_aggregations',
        'planned_start', 
        'actual_start',
        'start_date',
        'planned_end',
        'actual_end',
        'end_date',
        'is_searchable')
    list_display = ['__unicode__']
    inlines = [
        ActivityDateInline,
        ActivityReportingOrganisationInline,
        ActivityParticipatingOrganisationInline,
        ActivityPolicyMarkerInline,
        ActivityRecipientCountryInline,
        ActivitySectorInline,
        ActivityRecipientRegionInline,
        BudgetInline,
        TitleInline,
        DescriptionInline,
        DocumentLinkInline,
        ResultInline,
        LocationInline,
        RelatedActivityInline,
        TransactionInline,
    ]
    #
    # def get_inline_instances(self, request, obj=None):
    #     if obj is None:
    #         return []
    #
    #     inline_instances = super(ActivityAdmin, self).get_inline_instances(request, obj)
    #
    #     return inline_instances

    def save_model(self, request, obj, form, change):
        super(ActivityAdmin, self).save_model(request, obj, form, change)

        if not change:
            title = Title()
            title.activity = obj
            title.save()

            description = Description()
            description.activity = obj
            description.save()


class SectorAdmin(admin.ModelAdmin):
    search_fields = ['id']
    list_display = ['code', 'name', 'description', 'category']



class TransactionAdmin(ExtraNestedModelAdmin):
    search_fields = ['activity__id']
    readonly_fields = ['activity']
    list_display = ['__unicode__']
    exclude = ('value_string',)
    inlines = [
        TransactionDescriptionInline,
        TransactionProviderInline,
        TransactionReceiverInline,
    ]

    raw_id_fields = ('activity', 'recipient_country')

    autocomplete_lookup_fields = {
        'fk': ['activity', 'recipient_country'],

    }

    def get_object(self, request, object_id, from_field=None):
        obj = super(TransactionAdmin, self).get_object(request, object_id)

        if not getattr(obj, 'description', None):
            description = TransactionDescription()
            description.transaction = obj
            description.save()
            obj.description = description

        if not getattr(obj, 'receiver_organisation', None):
            transaction_receiver = TransactionReceiver()
            transaction_receiver.transaction = obj
            transaction_receiver.save()
            obj.receiver_organisation = transaction_receiver

        if not getattr(obj, 'provider_organisation', None):
            transaction_provider = TransactionProvider()
            transaction_provider.transaction = obj
            transaction_provider.save()
            obj.provider_organisation = transaction_provider

        return obj

    def save_model(self, request, obj, form, change):

        super(TransactionAdmin, self).save_model(request, obj, form, change)

        if not change:
            description = TransactionDescription()
            description.transaction = obj
            description.save()

            transaction_provider = TransactionProvider()
            transaction_provider.transaction = obj
            transaction_provider.save()

            transaction_receiver = TransactionReceiver()
            transaction_receiver.transaction = obj
            transaction_receiver.save()



class ResultIndicatorInline(NestedTabularInline):
    model = ResultIndicator
    inlines = [
        # TO DO:
        # ResultIndicatorTitleInline,
        # ResultIndicatorDescriptionInline,
        # ResultIndicatorBaselineInline,
        # ResultIndicatorPeriodInline,
    ]

    extra = 0

class ResultAdmin(ExtraNestedModelAdmin):
    search_fields = ['activity__id']
    readonly_fields = ['activity']
    list_display = ['__unicode__']
    inlines = [
        ResultIndicatorInline,
    ]

    raw_id_fields = ('activity',)

    autocomplete_lookup_fields = {
        'fk': ['activity'],

    }


admin.site.register(Activity, ActivityAdmin)
admin.site.register(Sector, SectorAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(Result, ResultAdmin)
admin.site.register(Narrative)
