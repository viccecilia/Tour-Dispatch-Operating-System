# PDF font asset

`NotoSansJP-VF.ttf` is bundled for Japanese document titles, labels and instructions.
`NotoSansSC-VF.ttf` is bundled for server data that may contain Chinese names or remarks.

The V0.14 hire renderer uses build-time static instances rather than registering the
variable fonts directly. Run `scripts/build_v014_font_instances.py` with FontTools in
an isolated build environment to create:

- `NotoSansJP-Regular.ttf` (wght 400)
- `NotoSansJP-Bold.ttf` (wght 700)
- `NotoSansSC-Regular.ttf` (wght 400)
- `NotoSansSC-Bold.ttf` (wght 700)

`V014_FONT_INSTANCES.json` records the source and generated SHA-256 values. Runtime PDF
generation does not require FontTools.

The PDF generator never relies on fonts installed on the server or on the driver's device.
