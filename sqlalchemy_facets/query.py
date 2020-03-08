from typing import List, Tuple
from functools import wraps
from collections import OrderedDict

from sqlalchemy.orm import Query
from sqlalchemy import func, distinct

from .facet import Facet
from .types import FacetedResult, FacetResult
from .utils import get_column, get_primary_key


class FacetedQueryMeta(type):

    def __init__(cls, classname, bases, dict_):
        cls.setup_facets(cls, cls.__dict__)
        type.__init__(cls, classname, bases, dict_)

    @staticmethod
    def setup_facets(cls, dict_):
        setattr(cls, "_facets", OrderedDict())
        for k, class_attribute in dict_.items():
            if isinstance(class_attribute, Facet):
                cls._facets[k] = class_attribute
                class_attribute.name = k


class FacetedQuery(metaclass=FacetedQueryMeta):

    def __init__(self, query: Query):
        self.base = query


    def __getattr__(self, item):
        base_item = getattr(self.base, item)
        if not callable(base_item):
            return base_item

        @wraps(base_item)
        def wrapped(*args, **kwargs):
            self.base = base_item(*args, **kwargs)
            return self
        return wrapped


    def facets_query(self):
        base = self.base.cte()
        facet_columns = [
            f.facet_column(base)
            for f in self._facets.values()
        ]
        count_field = get_primary_key(base)
        count_column = get_column(base, count_field)

        return self.session.query(
            *[*facet_columns, func.count(distinct(count_column))]
        ).group_by(func.grouping_sets(*facet_columns))


    def facets(self):
        return self.formatter(self.facets_query() if self._facets else [()])


    def formatter(self, raw_result: List[Tuple]) -> List[FacetResult]:
        raw_facets = list(zip(*raw_result)) or [()] * (len(self._facets) + 1)

        return [
            FacetResult.from_dual_sequences(
                facet=facet,
                values=raw_facets[i],
                counts=raw_facets[-1]
            )
            for i, facet in enumerate(self._facets.values())
        ]


    def all(self):
        return FacetedResult(
            base_result=self.base.all(),
            facets=self.facets()
        )



