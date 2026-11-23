Auto-detection of boolean arrays passed to contour()
-----------------------------------------------------

When a boolean array is passed to `~.Axes.contour` (or `~.Axes.tricontour`)
without explicit levels, a single level at 0.5 is now used, drawing the
boundary between the True and False regions.  For `~.Axes.contourf` and
`~.Axes.tricontourf` the levels default to ``[0, 0.5, 1]``.

.. code-block:: python

    ii, jj = np.ogrid[:100, :100]
    im = (ii + jj) % 20 < 10
    plt.contour(im)  # equivalent to plt.contour(im, levels=[.5])
