Default contour levels for boolean arrays
----------------------------------------
`~.Axes.contour` now defaults to the single level ``0.5`` for boolean input
arrays, drawing the boundary between False and True regions.
`~.Axes.contourf` defaults to levels ``[0, 0.5, 1]``. Explicitly supplied
levels are unchanged.
