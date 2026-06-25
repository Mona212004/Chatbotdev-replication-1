import torch
import multiprocessing


def get_device():
    if torch.cuda.is_available():
        num_gpus = torch.cuda.device_count()
        print(
            f"Detected {num_gpus} CUDA devices: {[torch.cuda.get_device_name(i) for i in range(num_gpus)]}"
        )
        devices = [f"cuda:{i}" for i in range(num_gpus)]
    elif torch.backends.mps.is_available():
        num_mps = torch.mps.device_count()
        print(
            f"Detected {num_mps} MPS devices: {'Apple silicon GPU' if num_mps>0 else 'N/A'}"
        )
        devices = ["mps"] * num_mps  # Typically 1 device
    else:
        print("No MPS detected; using CPU.")
        # Single 'cpu' entry — multi-process pooling on CPU forks processes that
        # share model weights via /dev/shm, which Docker containers cap at 64MB.
        # There is no throughput benefit to CPU parallelism here anyway.
        devices = ["cpu"]
    return devices


if __name__ == "__main__":
    devices = get_device()
    print(f"Devices selected for use: {devices}")
