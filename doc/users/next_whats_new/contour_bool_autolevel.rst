Auto-detection of boolean arrays in contour plots
-------------------------------------------------

If the input array to `~.Axes.contour` (and `~.Axes.contourf`,
`~.Axes.tricontour`, `~.Axes.tricontourf`) is a boolean array and no *levels*
are given, the levels now default to ``[0.5]`` for line contours and
``[0, 0.5, 1]`` for filled contours, so that the boundary between the True and
False regions is drawn, instead of the default set of automatic levels.

.. plot::
    :include-source: true
    :alt: Two images; on the left, a contour drawn with automatic levels; on the right, the boundary between True and False regions of a boolean array.

    from matplotlib import pyplot as plt
    import numpy as np

    ii, jj = np.ogrid[:100, :100]
    im = (ii + jj) % 20 < 10
    fig, axs = plt.subplots(1, 2, figsize=(5, 2.5), layout='constrained')
    axs[0].contour(im.astype(float))
    axs[0].set_title('float input')
    axs[1].contour(im)
    axs[1].set_title('boolean input, levels=[0.5]')
