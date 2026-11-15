"""visiontest — a self-administered distortion atlas for a high-PPI panel.

The package is split so that everything except :mod:`visiontest.backends`
imports and renders without a display:

* :mod:`visiontest.geometry`    – px / mm / degree / arcmin conversions
* :mod:`visiontest.calibration` – stored pixels-per-millimetre value
* :mod:`visiontest.params`      – pattern parameters and the control map
* :mod:`visiontest.patterns`    – pure numpy pattern renderers
* :mod:`visiontest.fixation`    – central fixation mark
* :mod:`visiontest.ui`          – session state, key dispatch, overlay
* :mod:`visiontest.export`      – PNG + JSON session export
* :mod:`visiontest.backends`    – presentation backends (Qt)

visiontest supports observation of visual distortion. It is not a medical
device and its output is not a diagnosis.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
