# If on Python 2.X
from __future__ import print_function

import pysolr
from django.conf import settings

from iati.models import Result
from solr.result.indexing import ResultIndexing
from solr.tasks import BaseTaskIndexing

solr = pysolr.Solr(
    '{url}/{core}'.format(
        url=settings.SOLR.get('url'),
        core=settings.SOLR.get('cores').get('result')
    ), always_commit=True, timeout=180
)


class ResultTaskIndexing(BaseTaskIndexing):
    indexing = ResultIndexing
    model = Result
    solr = solr

    def run_from_activity(self, activity):
        for result in activity.result_set.all():
            self.instance = result
            self.run()
