Auto-detection of boolean arrays passed to contour()
----------------------------------------------------

Boolean arrays passed to `~.Axes.contour` (and `~.Axes.tricontour`) now
default to a single contour level at 0.5, i.e. the boundary between True and
False regions; `~.Axes.contourf` (and `~.Axes.tricontourf`) default to levels
``[0, 0.5, 1]``. Explicitly passed levels are still honored.
