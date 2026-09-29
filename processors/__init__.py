from . import core, filters, utils
from . import advanced_filters
from . import checksum, compare, histogram, shapes, gradients, stitch, ascii, batch, barcode, lut
from . import ai

from .filter_defs import (
    FilterCategory,
    FilterDef,
    FilterDefRegistry,
    FilterParam,
    ALL_FILTERS_COMPAT,
    build_legacy_compat_layer,
    register_filter,
    register_legacy_filters,
)
from .filter_chain import FilterChain, FilterStep, FilterStepError, SCHEMA_VERSION
from .filter_presets import (
    save_preset, load_preset, load_preset_from_path,
    list_presets, delete_preset, preset_exists,
)
from .batch_filter_chain import (
    run_batch_filter_chain, BatchFilterChainResult, BatchItemResult, BatchItemStatus,
)
from . import filter_registry

advanced_filters.register_all()

_filter_defs_count = filter_registry.register_curated_filters()
_legacy_count = register_legacy_filters(filters.ALL_FILTERS)
build_legacy_compat_layer()

filters.ALL_FILTERS.clear()
filters.ALL_FILTERS.update(ALL_FILTERS_COMPAT)

__all__ = [
    "core", "filters", "utils",
    "advanced_filters", "checksum", "compare", "histogram", "shapes",
    "gradients", "stitch", "ascii", "batch", "barcode", "lut", "ai",
    "FilterCategory", "FilterDef", "FilterDefRegistry", "FilterParam",
    "register_filter", "register_legacy_filters",
    "FilterChain", "FilterStep", "FilterStepError", "SCHEMA_VERSION",
    "save_preset", "load_preset", "load_preset_from_path",
    "list_presets", "delete_preset", "preset_exists",
    "run_batch_filter_chain", "BatchFilterChainResult", "BatchItemResult", "BatchItemStatus",
]
