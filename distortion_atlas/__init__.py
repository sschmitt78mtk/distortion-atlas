"""distortion-atlas — a self-administered distortion atlas for a high-PPI panel.

The package is split so that everything except :mod:`distortion_atlas.backends`
imports and renders without a display:

* :mod:`distortion_atlas.geometry`    – px / mm / degree / arcmin conversions
* :mod:`distortion_atlas.calibration` – stored pixels-per-millimetre value
* :mod:`distortion_atlas.params`      – pattern parameters and the control map
* :mod:`distortion_atlas.patterns`    – pure numpy pattern renderers
* :mod:`distortion_atlas.fixation`    – central fixation mark
* :mod:`distortion_atlas.ui`          – session state, key dispatch, overlay
* :mod:`distortion_atlas.export`      – PNG + JSON session export
* :mod:`distortion_atlas.backends`    – presentation backends (Qt)

distortion-atlas supports observation of visual distortion. It is not a medical
device and its output is not a diagnosis.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
