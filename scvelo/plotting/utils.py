from .. import settings
from .. import logging as logg
from ..tools.utils import strings_to_categoricals
from . import palettes

import os
import numpy as np
import matplotlib.pyplot as pl
from matplotlib.ticker import MaxNLocator
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from matplotlib.colors import is_color_like, ListedColormap, to_rgb, cnames
from matplotlib.collections import LineCollection
import matplotlib.transforms as tx
from matplotlib import rcParams
from scipy.sparse import issparse
from cycler import Cycler, cycler


def make_dense(X):
    XA = X.A if issparse(X) and X.ndim == 2 else X.A1 if issparse(X) or isinstance(X, np.matrix) else X
    return np.array(XA)


def is_categorical(adata, c):
    from pandas.api.types import is_categorical as cat
    strings_to_categoricals(adata)
    str_not_var = isinstance(c, str) and c not in adata.var_names
    return str_not_var and (c in adata.obs.keys() and cat(adata.obs[c]) or is_color_like(c))


def n_categories(adata, c):
    from pandas.api.types import is_categorical as cat
    return len(adata.obs[c].cat.categories) if (c in adata.obs.keys() and cat(adata.obs[c])) else 0


def default_basis(adata):
    keys = [key for key in ['pca', 'tsne', 'umap'] if 'X_' + key in adata.obsm.keys()]
    if not keys:
        raise ValueError('No basis specified.')
    return keys[-1] if len(keys) > 0 else None


def check_basis(adata, basis):
    if basis in adata.obsm.keys() and 'X_' + basis not in adata.obsm.keys():
        adata.obsm['X_' + basis] = adata.obsm[basis]
        logg.info('Renamed', '\'' + basis + '\'', 'to convention', '\'X_' + basis + '\' (adata.obsm).')


def get_basis(adata, basis):
    if isinstance(basis, str) and basis.startswith('X_'):
        basis = basis[2:]
    check_basis(adata, basis)
    return basis


def make_unique_list(key, allow_array=False):
    from pandas import unique, Index
    if isinstance(key, Index): key = key.tolist()
    is_list = isinstance(key, (list, tuple, np.record)) if allow_array else isinstance(key, (list, tuple, np.ndarray, np.record))
    is_list_of_str = is_list and all(isinstance(item, str) for item in key)
    return unique(key) if is_list_of_str else key if is_list and len(key) < 20 else [key]


def make_unique_valid_list(adata, keys):
    keys = make_unique_list(keys)
    if all(isinstance(item, str) for item in keys):
        for i, key in enumerate(keys):
            if key.startswith('X_'):
                keys[i] = key = key[2:]
            check_basis(adata, key)
        valid_keys = np.hstack([adata.obs.keys(), adata.var.keys(), adata.varm.keys(), adata.obsm.keys(),
                                [key[2:] for key in adata.obsm.keys()], list(adata.layers.keys())])
        keys_ = keys
        keys = [key for key in keys if key in valid_keys or key in adata.var_names]
        keys_ = [key for key in keys_ if key not in keys]
        if len(keys_) > 0:
            logg.warn(', '.join(keys_), 'not found.')
    return keys


def update_axes(ax, xlim=None, ylim=None, fontsize=None, is_embedding=False, frameon=None):
    if xlim is not None:
        ax.set_xlim(xlim)
    if ylim is not None:
        ax.set_ylim(ylim)

    frameon = settings._frameon if frameon is None else frameon
    if frameon:
        if is_embedding:
            ax.tick_params(which='both', bottom=False, left=False, labelbottom=False, labelleft=False)
        else:
            ax.xaxis.set_major_locator(MaxNLocator(nbins=3, integer=True))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=3, integer=True))
            labelsize = int(fontsize * .75) if fontsize is not None else None
            ax.tick_params(axis='both', which='major', labelsize=labelsize)
    else:
        ax.set_xlabel('')
        ax.set_ylabel('')
        ax.tick_params(which='both', bottom=False, left=False, labelbottom=False, labelleft=False)
        ax.set_frame_on(False)

    return ax


def set_label(xlabel, ylabel, fontsize=None, basis=None, ax=None):
    if ax is None: ax = pl.gca()
    if isinstance(xlabel, str):
        ax.set_xlabel(xlabel.replace('_', ' '), fontsize=fontsize)
    if isinstance(ylabel, str):
        ax.set_ylabel(ylabel.replace('_', ' '), fontsize=fontsize, rotation=0 if ylabel.startswith('$') else 90)
    elif basis is not None:
        component_name = ('DC' if 'diffmap' in basis else 'tSNE' if basis == 'tsne' else 'UMAP' if basis == 'umap'
        else 'PC' if basis == 'pca' else basis.replace('draw_graph_', '').upper() if 'draw_graph' in basis else basis)
        ax.set_xlabel(component_name + '1')
        ax.set_ylabel(component_name + '2')


def set_title(title, layer=None, color=None, fontsize=None, ax=None):
    if ax is None: ax = pl.gca()
    color = color if isinstance(color, str) and not is_color_like(color) else None
    title = title if isinstance(title, str) and not is_color_like(title) else None
    if isinstance(title, str):
        title = title.replace('_', ' ')
    elif isinstance(layer, str) and isinstance(color, str):
        title = (color + ' ' + layer).replace('_', ' ')
    elif isinstance(color, str):
        title = color.replace('_', ' ')
    else:
        title = ''
    ax.set_title(title, fontsize=fontsize)


def set_frame(ax, frameon):
    frameon = settings._frameon if frameon is None else frameon
    if not frameon:
        ax.set_xlabel('')
        ax.set_ylabel('')
        ax.set_frame_on(False)
    return ax


def default_size(adata):
    adjusted, classic = 1.2e5 / adata.n_obs, 20
    return np.mean([adjusted, classic]) if settings._rcParams_style == 'scvelo' else adjusted


def default_color(adata):
    return 'clusters' if 'clusters' in adata.obs.keys() else 'louvain' if 'louvain' in adata.obs.keys() else 'grey'


def default_color_map(adata, c):
    cmap = None
    if isinstance(c, str) and c in adata.obs.keys() and not is_categorical(adata, c): c = adata.obs[c]
    if len(np.array(c).flatten()) == adata.n_obs:
        if np.min(c) in [-1, 0, False] and np.max(c) in [1, True]: cmap = 'viridis_r'
    return cmap


def default_legend_loc(adata, color, legend_loc):
    if legend_loc is False:
        legend_loc = 'none'
    elif legend_loc is None:
        legend_loc = 'upper right' if n_categories(adata, color) <= 4 else 'on data'
    return legend_loc


def clip(c, perc):
    if np.size(perc) < 2: perc = [perc, 100] if perc < 50 else [0, perc]
    lb, ub = np.percentile(c, perc)
    return np.clip(c, lb, ub)


def get_colors(adata, c):
    if is_color_like(c):
        return c
    else:
        if c+'_colors' not in adata.uns.keys():
            palette = default_palette(None)
            palette = adjust_palette(palette, length=len(adata.obs[c].cat.categories))
            adata.uns[c + '_colors'] = palette[:len(adata.obs[c].cat.categories)].by_key()['color']
        cluster_ix = adata.obs[c].cat.codes.values
        return np.array([adata.uns[c + '_colors'][cluster_ix[i]] for i in range(adata.n_obs)])


def interpret_colorkey(adata, c=None, layer=None, perc=None):
    if c is None: c = default_color(adata)
    if issparse(c): c = make_dense(c).flatten()
    if is_categorical(adata, c): c = get_colors(adata, c)
    elif isinstance(c, str):
        if c in adata.obs.keys():  # color by observation key
            c = adata.obs[c]
        elif c in adata.var_names:  # color by var in specific layer
            c = adata[:, c].layers[layer] if layer in adata.layers.keys() else adata[:, c].X
            c = c.A.flatten() if issparse(c) else c
        elif c in adata.var.keys():  # color by observation key
            c = adata.var[c]
        else:
            raise ValueError('color key is invalid! pass valid observation annotation or a gene name')
        if perc is not None: c = clip(c, perc=perc)
    else:
        c = np.array(c).flatten()
        if perc is not None: c = clip(c, perc=perc)
    return c


def get_components(components=None, basis=None, projection=None):
    if components is None: components = '1,2,3' if projection == '3d' else '1,2'
    if isinstance(components, str): components = components.split(',')
    components = np.array(components).astype(int) - 1
    if 'diffmap' in basis or 'vmap' in basis: components += 1
    return components


def set_colorbar(smp, ax, orientation='vertical', labelsize=None):
    cb = pl.colorbar(smp, orientation=orientation, cax=inset_axes(ax, width="2%", height="30%", loc=4, borderpad=0))
    cb.set_alpha(1)
    cb.ax.tick_params(labelsize=labelsize)
    cb.draw_all()
    cb.locator = MaxNLocator(nbins=3, integer=True)
    cb.update_ticks()


def default_arrow(size):
    if isinstance(size, (list, tuple)) and len(size) == 3:
        head_l, head_w, ax_l = size
    elif type(size) == int or type(size) == float:
        head_l, head_w, ax_l = 12 * size, 10 * size, 8 * size
    else:
        head_l, head_w, ax_l = 12, 10, 8
    return head_l, head_w, ax_l


def velocity_embedding_changed(adata, basis, vkey):
    if 'X_' + basis not in adata.obsm.keys(): changed = False
    else:
        changed = vkey + '_' + basis not in adata.obsm_keys()
        if vkey + '_settings' in adata.uns.keys():
            sett = adata.uns[vkey + '_settings']
            changed |= 'embeddings' not in sett or basis not in sett['embeddings']
    return changed


def savefig_or_show(writekey=None, show=None, dpi=None, ext=None, save=None):
    if isinstance(save, str):
        # check whether `save` contains a figure extension
        if ext is None:
            for try_ext in ['.svg', '.pdf', '.png']:
                if save.endswith(try_ext):
                    ext = try_ext[1:]
                    save = save.replace(try_ext, '')
                    break
        # append it
        writekey = (writekey + '_' if writekey is not None and len(writekey) > 0 else '') + save
        save = True
    save = settings.autosave if save is None else save
    show = settings.autoshow if show is None else show

    if save:
        if dpi is None:
            # we need this as in notebooks, the internal figures are also influenced by 'savefig.dpi' this...
            if not isinstance(rcParams['savefig.dpi'], str) and rcParams['savefig.dpi'] < 150:
                if settings._low_resolution_warning:
                    logg.warn(
                        'You are using a low resolution (dpi<150) for saving figures.\n'
                        'Consider running `set_figure_params(dpi_save=...)`, which will '
                        'adjust `matplotlib.rcParams[\'savefig.dpi\']`')
                    settings._low_resolution_warning = False
            else:
                dpi = rcParams['savefig.dpi']
        if not os.path.exists(settings.figdir): os.makedirs(settings.figdir)
        if ext is None: ext = settings.file_format_figs
        filename = settings.figdir + f'{settings.plot_prefix}{writekey}{settings.plot_suffix}.{ext}'
        logg.msg('saving figure to file', filename, v=1)
        pl.savefig(filename, dpi=dpi, bbox_inches='tight')

    if show: pl.show()
    if save: pl.close()  # clear figure


def default_palette(palette=None):
    if palette is None: return rcParams['axes.prop_cycle']
    elif not isinstance(palette, Cycler): return cycler(color=palette)
    else: return palette


def adjust_palette(palette, length):
    islist = False
    if isinstance(palette, list):
        islist = True
    if ((islist and len(palette) < length)
       or (not isinstance(palette, list) and len(palette.by_key()['color']) < length)):
        if length <= 28:
            palette = palettes.default_26
        elif length <= len(palettes.default_64):  # 103 colors
            palette = palettes.default_64
        else:
            palette = ['grey' for i in range(length)]
            logg.info('more than 103 colors would be required, initializing as \'grey\'')
        return palette if islist else cycler(color=palette)
    elif islist:
        return palette
    elif not isinstance(palette, Cycler):
        return cycler(color=palette)
    else:
        return palette


def rgb_custom_colormap(colors=['royalblue', 'white', 'forestgreen'], alpha=None, N=256):
    """Creates a custom colormap with the given colors. Colors can be given as names or as rgb values.

    Arguments
    ---------
    colors: : `list` or `array` (default `['royalblue', 'white', 'forestgreen']`)
        List of colors, either as names or rgb values.
    alpha: `list`, `np.ndarray` or `None` (default: `None`)
        Alpha of the colors. Must be same length as colors.
    N: `int` (default: `256`)
        y coordinate

    Returns
    -------
        A ListedColormap
    """
    c = []
    for color in colors:
        if type(color) is str:
            c.append(to_rgb(cnames[color]))

    vals = np.ones((N, 4))
    ints = len(c) - 1
    n = int(N / ints)

    alpha = np.ones(len(c)) if alpha is None else alpha

    for j in range(ints):
        for i in range(3):
            vals[n * j:n * (j + 1), i] = np.linspace(c[j][i], c[j + 1][i], n)
        vals[n * j:n * (j + 1), -1] = np.linspace(alpha[j], alpha[j + 1], n)
    return ListedColormap(vals)


def get_temporal_connectivities(adata, tkey, n_convolve=30):
    from ..preprocessing.moments import get_connectivities
    from ..tools.velocity_graph import vals_to_csr
    from ..tools.utils import normalize, get_indices

    #c_idx = get_indices(get_connectivities(adata, recurse_neighbors=True))[0]
    #c_idx = np.hstack([c_idx, np.linspace(0, len(c_idx) - 1, len(c_idx), dtype=int)[:, None]])

    rows, cols, vals, n_obs, n_convolve = [], [], [], len(tkey), int(n_convolve / 2)
    for i in range(n_obs):
        i_max = None if i + n_convolve >= n_obs else i + n_convolve
        i_min = np.max([0, i - n_convolve])
        t_idx = np.argsort(tkey)[i_min: i_max]  # temporal neighbourhood
        #t_idx = np.intersect1d(t_idx, c_idx[i])
        rows.extend(np.ones(len(t_idx), dtype=int) * np.argsort(tkey)[i])
        cols.extend(t_idx)
        vals.extend(np.ones(len(t_idx), dtype=int))

    c_conn = get_connectivities(adata, recurse_neighbors=True)
    t_conn = vals_to_csr(vals, rows, cols, shape=(n_obs, n_obs))
    return normalize(t_conn)  # normalize(t_conn.multiply(c_conn))


def plot_linear_fit(adata, basis, vkey, xkey, linewidth=1):
    xnew = np.linspace(0, np.percentile(make_dense(adata[:, basis].layers[xkey]), 98))
    vkeys = adata.layers.keys() if vkey is None else make_unique_list(vkey)
    fits = [fit for fit in vkeys if all(['velocity' in fit, fit + '_gamma' in adata.var.keys()])]
    for i, fit in enumerate(fits):
        linestyle = '--' if 'variance_' + fit in adata.layers.keys() else '-'
        gamma = adata[:, basis].var[fit + '_gamma'].values if fit + '_gamma' in adata.var.keys() else 1
        beta = adata[:, basis].var[fit + '_beta'].values if fit + '_beta' in adata.var.keys() else 1
        offset = adata[:, basis].var[fit + '_offset'].values if fit + '_offset' in adata.var.keys() else 0
        pl.plot(xnew, gamma / beta * xnew + offset / beta, linestyle=linestyle, linewidth=linewidth,
                c='k' if i == 0 else None)
        fits[i] = 'steady-state ratio ({})'.format(fit) if len(fits) > 1 else 'steady-state ratio'
    return fits


def plot_density(x, y=None, eval_pts=50, scale=10, alpha=.3, color='grey', ax=None):
    from scipy.stats import gaussian_kde as kde
    if ax is None: ax = pl.gca()

    # density plot along x-coordinate
    xnew = np.linspace(min(x), max(x), eval_pts)
    vals = kde(x)(xnew)

    if y is not None:
        offset = max(y) / scale
        scale_s = offset / np.max(vals)
        offset *= 1.3
        vals = vals * scale_s - offset
    else:
        offset = 0

    ax.plot(xnew, vals, color=color)
    ax.fill_between(xnew, -offset, vals, alpha=alpha, color=color)
    ax.set_ylim(-offset)

    # density plot along y-coordinate
    if y is not None:
        ynew = np.linspace(min(y), max(y), eval_pts)
        vals = kde(y)(ynew)

        offset = max(x) / scale
        scale_u = offset / np.max(vals)
        offset *= 1.3
        vals = vals * scale_u - offset

        ax.plot(vals, ynew, color=color)
        ax.fill_betweenx(ynew, -offset, vals, alpha=alpha, color=color)
        ax.set_xlim(-offset)


def rugplot(x, height=.03, color=None, ax=None, **kwargs):
    if ax is None: ax = pl.gca()
    x = np.asarray(x)

    transform = tx.blended_transform_factory(ax.transData, ax.transAxes)
    line_segs = np.column_stack([np.repeat(x, 2), np.tile([0, height], len(x))]).reshape([len(x), 2, 2])
    ax.add_collection(LineCollection(line_segs, transform=transform, color=color, **kwargs))
    ax.autoscale_view(scalex=True, scaley=False)
    return ax


def hist(arrays, alpha=.5, bins=50, colors=None, labels=None, hist=None, kde=None, bw_method=None, xlabel=None,
         ylabel=None, xlim=None, ylim=None, cutoff=None, xscale=None, yscale=None, fontsize=None, legend_fontsize=None,
         figsize=None, norm=None, perc=None, exclude_zeros=None, axvline=None, axhline=None, ax=None, dpi=None,
         show=True):
    """\
    Plot a histogram.

    Arguments
    ---------
    arrays: : `list` or `array` (default `['royalblue', 'white', 'forestgreen']`)
        List of colors, either as names or rgb values.
    alpha: `list`, `np.ndarray` or `None` (default: `None`)
        Alpha of the colors. Must be same length as colors.
    bins : `int` or `sequence` (default: `50`)
        If an integer is given, ``bins + 1`` bin edges are calculated and
        returned, consistent with `numpy.histogram`.
        If `bins` is a sequence, gives bin edges, including left edge of
        first bin and right edge of last bin.  In this case, `bins` is
        returned unmodified.
    colors: : `list` or `array` (default `['royalblue', 'white', 'forestgreen']`)
        List of colors, either as names or rgb values.
    labels : str or None (default: `None`)
            String, or sequence of strings to label clusters.
    hist: `bool` or `None` (default: `None`)
        Whether to show histogram.
    kde: `bool` or `None` (default: `None`)
        Whether to use kernel density estimation on data.
    bw_method : `str`, `scalar` or `callable`, (default: `None`)
        The method used to calculate the estimator bandwidth.  This can be
        'scott', 'silverman', a scalar constant or a callable.  If a
        scalar, this will be used directly as `kde.factor`.  If a callable,
        it should take a `gaussian_kde` instance as only parameter and
        return a scalar.  If None (default), nothing happens; the current
        `kde.covariance_factor` method is kept.
    xlabel: `str` (default: `None`)
        Label of x-axis.
    ylabel: `str` (default: `None`)
        Label of y-axis.
    xlim: tuple, e.g. [0,1] or `None` (default: `None`)
        Restrict x-limits of the axis.
    ylim: tuple, e.g. [0,1] or `None` (default: `None`)
        Restrict y-limits of the axis.
    cutoff: tuple, e.g. [0,1] or `float` or `None` (default: `None`)
        Bins will be cut off below and above the cutoff values.
    xscale: `log` or `None` (default: `None`)
        Scale of the x-axis.
    yscale: `log` or `None` (default: `None`)
        Scale of the y-axis.
    fontsize: `float` (default: `None`)
        Label font size.
    legend_fontsize: `int` (default: `None`)
        Legend font size.
    figsize: tuple (default: `(7,5)`)
        Figure size.
    norm: `bool` or `None` (default: `None`)
        Whether to normalize data.
    perc: tuple, e.g. [2,98] (default: `None`)
        Specify percentile for continuous coloring.
    exclude_zeros: `bool` or `None` (default: `None`)
        Whether to exclude zeros in data for the kde and hist plot.
    axvline: `float` or `None` (default: `None`)
        Plot a vertical line at the specified x-value.
    axhline `float` or `None` (default: `None`)
        Plot a horizontal line at the specified y-value.
    ax: `matplotlib.Axes`, optional (default: `None`)
        A matplotlib axes object. Only works if plotting a single component.
    dpi: `int` (default: 80)
        Figure dpi.
    show: `bool`, optional (default: `None`)
        Show the plot, do not return axis.

    Returns
    -------
        If `show==False` a `matplotlib.Axis`
    """

    if ax is None:
        fig, ax = pl.subplots(figsize=figsize, dpi=dpi)

    arrays = arrays if isinstance(arrays, (list, tuple)) or arrays.ndim > 1 else [arrays]
    if norm is None: norm = kde
    if hist is None: hist = not kde

    palette = default_palette(None).by_key()['color'][::-1]
    colors = palette if colors is None or len(colors) < len(arrays) else colors

    masked_arrays = np.ma.masked_invalid(arrays)
    bmin, bmax = masked_arrays.min(), masked_arrays.max()
    if xlim is not None:
        bmin, bmax = max(bmin, xlim[0]), min(bmax, xlim[1])
    elif perc is not None:
        if np.size(perc) < 2: perc = [perc, 100] if perc < 50 else [0, perc]
        bmin, bmax = np.nanpercentile(arrays, perc)
    bins = np.arange(bmin, bmax + (bmax - bmin) / bins, (bmax - bmin) / bins)

    if xscale is 'log':
        bins = bins[bins > 0]
        bins = np.logspace(np.log10(bins[0]), np.log10(bins[-1]), len(bins))

    if cutoff is not None:
        bins = bins[(bins > cutoff[0]) & (bins < cutoff[1])] if isinstance(cutoff, list) else bins[bins < cutoff]

    for i, x in enumerate(arrays):
        x_vals = np.array(x[np.isfinite(x)])
        if exclude_zeros: x_vals = np.array(x_vals[x_vals != 0])
        if kde:
            from scipy.stats import gaussian_kde
            kde_bins = gaussian_kde(x_vals, bw_method=bw_method)(bins)
            if not norm:
                kde_bins *= (bins[1] - bins[0]) * len(x_vals)
            ax.plot(bins, kde_bins, color=colors[i])
            ax.fill_between(bins, 0, kde_bins, alpha=.4, color=colors[i],
                            label=labels[i] if labels is not None else None)
            ylim = np.min(kde_bins) if ylim is None else ylim
        if hist:
            if norm:
                x_vals /= (bins[1] - bins[0]) * len(x_vals)
            ax.hist(x_vals, bins=bins, alpha=alpha, color=colors[i],
                    label=labels[i] if labels is not None else None)

    set_label(xlabel if xlabel is not None else '', ylabel if xlabel is not None else '', fontsize=fontsize, ax=ax)

    if labels is not None:
        ax.legend(fontsize=legend_fontsize)

    if axvline: ax.axvline(axvline)
    if axhline: ax.axhline(axhline)

    if xscale is not None: ax.set_xscale(xscale)
    if yscale is not None: ax.set_yscale(yscale)

    update_axes(ax, xlim, ylim, fontsize, frameon=True)

    if not show:
        return ax
    else:
        pl.show()


def plot(arrays, normalize=False, colors=None, labels=None, xlabel=None, ylabel=None, xscale=None, yscale=None, ax=None,
         figsize=None, dpi=None, show=True):
    ax = pl.figure(None, figsize, dpi=dpi) if ax is None else ax
    arrays = np.array(arrays)
    arrays = arrays if isinstance(arrays, (list, tuple)) or arrays.ndim > 1 else [arrays]

    palette = default_palette(None).by_key()['color'][::-1]
    colors = palette if colors is None or len(colors) < len(arrays) else colors

    for i, array in enumerate(arrays):
        X = array[np.isfinite(array)]
        X = X / np.max(X) if normalize else X
        pl.plot(X, color=colors[i], label=labels[i] if labels is not None else None)

    pl.xlabel(xlabel if xlabel is not None else '')
    pl.ylabel(ylabel if xlabel is not None else '')
    if labels is not None: pl.legend()
    if xscale is not None: pl.xscale(xscale)
    if yscale is not None: pl.yscale(yscale)

    if not show:
        return ax
    else:
        pl.show()


def fraction_timeseries(adata, xkey='clusters', tkey='dpt_pseudotime', bins=30, legend_loc='best', title=None,
                        fontsize=None, ax=None, figsize=None, dpi=None, xlabel=None, ylabel=None, show=True):
    t = np.linspace(0, 1 + 1 / bins, bins)
    types = np.unique(adata.obs[xkey].values)

    y = []
    for i in range(bins - 1):
        mask = np.all([adata.obs[tkey].values <= t[i + 1], adata.obs[tkey].values > t[i]], axis=0)
        x = list(adata[mask].obs[xkey].values)
        y.append([])
        for name in types:
            occur = x.count(name)
            y[-1].append(occur)
        y[-1] /= np.sum(y[-1])
    y = np.array(y).T

    ax = pl.figure(figsize=figsize, dpi=dpi) if ax is None else ax

    pl.stackplot(t[:-1], y, baseline='zero', labels=types,
                 colors=adata.uns['clusters_colors'] if 'clusters_colors' in adata.uns.keys() else None,
                 edgecolor='white')

    pl.legend(types, loc=legend_loc)
    if title is not None:
        pl.title(title, fontsize=fontsize)
    pl.xlabel(tkey if xlabel is None else xlabel, fontsize=fontsize)
    pl.ylabel(xkey + ' fractions' if ylabel is None else ylabel, fontsize=fontsize)
    pl.xlim(adata.obs[tkey].values.min(), adata.obs[tkey].values.max())
    pl.ylim(0, 1)

    if not show:
        return ax
    else:
        pl.show()


# def phase(adata, var=None, x=None, y=None, color='louvain', fits='all', xlabel='spliced', ylabel='unspliced',
#           fontsize=None, show=True, ax=None, **kwargs):
#     if isinstance(var, str) and (var in adata.var_names):
#         if (x is None) or (y is None):
#             ix = np.where(adata.var_names == var)[0][0]
#             x, y = adata.layers['Ms'][:, ix], adata.layers['Mu'][:, ix]
#     else:
#         ValueError('var not found in adata.var_names.')
#
#     ax = scatter(adata, x=x, y=y, color=color, frameon=True, title=var, xlabel=xlabel, ylabel=ylabel, ax=ax, **kwargs)
#
#     xnew = np.linspace(0, x.max() * 1.02)
#     fits = adata.layers.keys() if fits == 'all' else fits
#     fits = [fit for fit in fits if 'velocity' in fit]
#     for fit in fits:
#         linestyle = '--' if 'stochastic' in fit else '-'
#         pl.plot(xnew, adata.var[fit+'_gamma'][ix] / adata.var[fit+'_beta'][ix] * xnew
#                 + adata.var[fit+'_offset'][ix] / adata.var[fit+'_beta'][ix], c='k', linestyle=linestyle)
#
#     if show: pl.show()
#     else: return ax