"""Per-stage step bodies for the ``BuildExecutor`` pipeline.

Each module in this package exposes a ``run(executor, ...)`` function that
implements one stage in ``lathe.executor.STAGE_ORDER``. The dispatcher in
``lathe.executor`` imports these modules and delegates to them, preserving
``BuildExecutor``'s public method signatures via thin wrappers.
"""
