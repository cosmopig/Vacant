Auto-selection of contour levels for boolean input
--------------------------------------------------

If the *Z* array passed to `~.Axes.contour` or `~.Axes.tricontour` is boolean
and no *levels* are given, a single level at 0.5 is used, drawing the boundary
between the False and True regions.  `~.Axes.contourf` and
`~.Axes.tricontourf` likewise default to levels ``[0, 0.5, 1]``.
