# Image AI model sources and licenses

The Python image inference modules in this directory are adapted from
[NextGenUp](https://github.com/riponcm/nextgenUp), release v1.2.2, under the
MIT license. See `UPSTREAM-LICENSE`.

Model weights are not part of the source checkout. They are downloaded only
after an authenticated user explicitly requests a model. Downloads are pinned
to immutable revisions and SHA-256 checked before use.

| Model | Model source | License metadata |
|---|---|---|
| BiRefNet Lite | [onnx-community/BiRefNet_lite](https://huggingface.co/onnx-community/BiRefNet_lite) | MIT |
| SCUNet | [Heliosoph/scunet-onnx](https://huggingface.co/Heliosoph/scunet-onnx) | Apache-2.0 |
| NAFNet deblur | [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/deblurring_nafnet) | MIT |
| DDColor tiny | [edgetools/ddcolor](https://huggingface.co/edgetools/ddcolor) | Apache-2.0 |
| LaMa ONNX | [Carve/LaMa-ONNX](https://huggingface.co/Carve/LaMa-ONNX) | Apache-2.0 |
| GFPGAN v1.4 | [TencentARC/GFPGAN](https://github.com/TencentARC/GFPGAN) model mirrored at [OwlMaster/AllFilesRope](https://huggingface.co/OwlMaster/AllFilesRope) | Apache-2.0 upstream; mirror metadata does not independently declare a license |
| YuNet face detector | [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) | MIT |

The weight-provider licenses and provenance can differ from the engine source
license. Review the linked upstream notices before redistributing downloaded
weights; PM Tools does not commit or redistribute those files.
