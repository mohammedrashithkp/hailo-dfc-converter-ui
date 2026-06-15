#!/usr/bin/env python3
"""
ONNX to HEF Conversion Script for Hailo-8
Converts a YOLOv8 ONNX model to Hailo Executable Format (.hef)

Pipeline: ONNX -> Parse (HAR) -> Optimize (Quantize) -> Compile (HEF)
"""

import os
import sys
import argparse
from pathlib import Path


def parse_onnx(onnx_path: str, hw_arch: str, input_height: int, input_width: int):
    """Step 1: Parse ONNX model into Hailo Archive (HAR) format."""
    from hailo_sdk_client import ClientRunner

    model_name = Path(onnx_path).stem
    har_path = f"/workspace/{model_name}_parsed.har"

    print(f"\n{'='*60}")
    print(f"STEP 1: Parsing ONNX -> HAR")
    print(f"  Model:      {onnx_path}")
    print(f"  HW Arch:    {hw_arch}")
    print(f"  Input Size: {input_height}x{input_width}")
    print(f"{'='*60}\n")

    runner = ClientRunner(hw_arch=hw_arch)

    # YOLOv8 models have post-processing layers (DFL, Reshape, Concat)
    # that are not supported on the Hailo HW. We specify end_node_names
    # to cut the graph before those layers. The post-processing will run
    # on the host CPU instead (handled by HailoRT / your application).
    end_node_names = [
        "/model.22/cv2.0/cv2.0.2/Conv",
        "/model.22/cv3.0/cv3.0.2/Conv",
        "/model.22/cv2.1/cv2.1.2/Conv",
        "/model.22/cv3.1/cv3.1.2/Conv",
        "/model.22/cv2.2/cv2.2.2/Conv",
        "/model.22/cv3.2/cv3.2.2/Conv",
    ]

    print(f"  Using end nodes: {end_node_names}")
    print(f"  (Post-processing will run on host CPU)")
    print()

    hn, npz = runner.translate_onnx_model(
        onnx_path,
        model_name,
        start_node_names=None,
        end_node_names=end_node_names,
        net_input_shapes={"images": [1, 3, input_height, input_width]},
    )

    runner.save_har(har_path)
    print(f"✅ Parsed HAR saved to: {har_path}")
    return har_path, runner


def optimize_model(har_path: str, hw_arch: str, calib_data_path: str = None, input_height: int = 640, input_width: int = 640):
    """Step 2: Optimize (quantize FP32 -> INT8) the HAR model."""
    from hailo_sdk_client import ClientRunner

    model_name = Path(har_path).stem.replace("_parsed", "")
    optimized_har_path = f"/workspace/{model_name}_optimized.har"

    print(f"\n{'='*60}")
    print(f"STEP 2: Optimizing (Quantization FP32 -> INT8)")
    print(f"  HAR Input:  {har_path}")
    if calib_data_path:
        print(f"  Calib Data: {calib_data_path}")
    else:
        print(f"  Calib Data: Random (for testing only)")
    print(f"{'='*60}\n")

    runner = ClientRunner(har=har_path, hw_arch=hw_arch)

    if calib_data_path and os.path.isdir(calib_data_path):
        # Use real calibration data
        import numpy as np
        from PIL import Image

        calib_images = []
        image_files = sorted(Path(calib_data_path).rglob("*"))
        image_extensions = {".jpg", ".jpeg", ".png", ".bmp"}

        for img_file in image_files:
            if img_file.suffix.lower() in image_extensions:
                img = Image.open(img_file).convert("RGB")
                img = img.resize((input_width, input_height))
                img_np = np.array(img).astype(np.float32) / 255.0
                calib_images.append(img_np)

        if calib_images:
            calib_dataset = np.stack(calib_images[:64])  # Use up to 64 images
            print(f"  Using {len(calib_dataset)} real calibration images")
            runner.optimize(calib_dataset)
        else:
            print("  ⚠️  No valid images found, falling back to random calibration")
            import numpy as np
            calib_dataset = np.random.rand(64, input_height, input_width, 3).astype(np.float32)
            runner.optimize(calib_dataset)
    else:
        # Use random calibration data (less accurate but works for testing)
        import numpy as np
        print("  Generating random calibration data (64 images)...")
        print("  ⚠️  For better accuracy, provide real images with --calib-data")
        calib_dataset = np.random.rand(64, input_height, input_width, 3).astype(np.float32)
        runner.optimize(calib_dataset)

    runner.save_har(optimized_har_path)
    print(f"✅ Optimized HAR saved to: {optimized_har_path}")
    return optimized_har_path, runner


def compile_model(har_path: str, hw_arch: str):
    """Step 3: Compile optimized HAR into HEF."""
    from hailo_sdk_client import ClientRunner

    model_name = Path(har_path).stem.replace("_optimized", "")
    hef_path = f"/workspace/{model_name}.hef"

    print(f"\n{'='*60}")
    print(f"STEP 3: Compiling HAR -> HEF")
    print(f"  HAR Input:  {har_path}")
    print(f"  HW Arch:    {hw_arch}")
    print(f"  Output:     {hef_path}")
    print(f"{'='*60}\n")

    runner = ClientRunner(har=har_path, hw_arch=hw_arch)
    runner.load_model_script("performance_param(compiler_optimization_level=max)")
    hef = runner.compile()

    with open(hef_path, "wb") as f:
        f.write(hef)

    file_size = os.path.getsize(hef_path)
    print(f"✅ HEF compiled successfully!")
    print(f"   Output: {hef_path}")
    print(f"   Size:   {file_size / (1024*1024):.2f} MB")
    return hef_path


def main():
    parser = argparse.ArgumentParser(description="Convert ONNX model to Hailo HEF")
    parser.add_argument("--onnx", type=str, default="/workspace/best.onnx",
                        help="Path to the ONNX model file")
    parser.add_argument("--hw-arch", type=str, default="hailo8",
                        choices=["hailo8", "hailo8l", "hailo10h"],
                        help="Target Hailo hardware architecture")
    parser.add_argument("--input-height", type=int, default=640,
                        help="Model input height")
    parser.add_argument("--input-width", type=int, default=640,
                        help="Model input width")
    parser.add_argument("--calib-data", type=str, default=None,
                        help="Path to calibration images directory (optional)")
    args = parser.parse_args()

    print("\n" + "🔧 " * 20)
    print("  HAILO ONNX -> HEF CONVERSION PIPELINE")
    print("🔧 " * 20 + "\n")

    # Step 1: Parse
    har_path, _ = parse_onnx(args.onnx, args.hw_arch, args.input_height, args.input_width)

    # Step 2: Optimize (Quantize)
    optimized_har_path, _ = optimize_model(har_path, args.hw_arch, args.calib_data, args.input_height, args.input_width)

    # Step 3: Compile
    hef_path = compile_model(optimized_har_path, args.hw_arch)

    print(f"\n{'='*60}")
    print(f"🎉 CONVERSION COMPLETE!")
    print(f"   HEF file: {hef_path}")
    print(f"   Copy this file to your Raspberry Pi 5 for inference.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
