# GenManip: LLM-driven Simulation for Generalizable Instruction-Following Manipulation 

<div align="center">

📄 **Official Project Page for CVPR 2025 Paper**  
🎥 Watch the demo video below to see **GenManip** in action!

<p align="center">
  <a href="https://www.youtube.com/watch?v=FnoFvzVlM6E" target="_blank">
    <img src="readme_assets/teaser.png" alt="GenManip Video" width="100%"/>
  </a>
</p>

[![Paper](https://img.shields.io/badge/Paper-arXiv%20\(CVPR%202025\)-blue)](https://arxiv.org/abs/2506.10966)
[![Project Page](https://img.shields.io/badge/Website-genmanip.axi404.top-%231877F2)](https://genmanip.axi404.top/)
[![Docs](https://img.shields.io/badge/Docs-Available-brightgreen)](https://genmanip.axi404.top/overview)

</div>

---

## 🧠 Overview

**GenManip** is a simulation platform designed for large-scale evaluation of **generalist robotic manipulation policies** under diverse, realistic instruction-following scenarios.

Built on [NVIDIA Isaac Sim](https://developer.nvidia.com/isaac-sim), **GenManip** provides:

- 🧠 **LLM-driven task generation** via a novel **Task-oriented Scene Graph (ToSG)**
- 🔬 **200 curated scenarios** for both modular and end-to-end policy benchmarking
- 🧱 **10,000+ rigid** and **100+ articulated** objects with vision-language annotations
- 🧭 Evaluation of **spatial**, **appearance**, **commonsense**, and **long-horizon reasoning**

---

## 🗞️ News & Updates

### 🔹 30 Oct 2025  
The **data synthesis process** and **evaluation code** for generalizable pick-and-place tasks have been released.

### 🔹 5 Aug 2025  
We’re thrilled to announce:
- **10 new post-training tasks** for dual-arm manipulation  
- **55K+ generalizable pick-and-place tasks** across ~14K objects on the **ALOHA platform**  
- Part of the **IROS 2025 Challenge: Vision-Language Manipulation in Open Tabletop Environments**

📌 **Challenge Registration:**  
[https://eval.ai/web/challenges/challenge-page/2626/overview](https://eval.ai/web/challenges/challenge-page/2626/overview)

<p align="center">
  <img src="readme_assets/iros-teaser.jpg" width="80%" alt="IROS 2025 Teaser"/>
</p>

---

## 📂 Data Access

- **Pre-training Data (Dual-arm Generalizable Pick-and-Place)**  
  [Hugging Face Dataset](https://huggingface.co/datasets/InternRobotics/IROS-2025-Challenge-Manip/tree/main)

- **Post-training Data (Dual-arm Manipulation, 10 Tasks)**  
  [Hugging Face Dataset](https://huggingface.co/datasets/InternRobotics/IROS-2025-Challenge-Manip/tree/main)

<video src="readme_assets/scaling_data.mp4" controls width="600"></video>

Additional resources:
- **GenManip Benchmark** will merge into [InternManip](https://github.com/InternRobotics/InternManip)
- **InternData-M1** dataset: [Hugging Face Link](https://huggingface.co/datasets/InternRobotics/InternData-M1)  
  Includes ~250K simulation demonstrations with:
  - 2D/3D bounding boxes  
  - Object trajectories  
  - Grasp points  
  - Semantic masks  

> ⚙️ Conversion from GenManip to LeRobot format is in progress. All data is generated and will be available soon, along with **long-horizon scaling data**.

---

## ✨ Key Features

| Feature | Description |
| -------- | ------------ |
| 🎯 **ToSG-based Task Synthesis** | Graph-based semantic representation for complex task generation |
| 🖼️ **Photorealistic Simulation** | RTX ray-traced rendering with physics-accurate realism |
| 📊 **Benchmark Suite** | 200+ high-diversity tasks with human-in-the-loop refinement |
| 🧪 **Evaluation Tools** | Supports SR, SPL, ablation studies, and generalization diagnostics |

---

## 🚀 Getting Started

Visit the **[official website](https://genmanip.axi404.top)** for setup guides, documentation, and usage examples.

---

## 🧩 TODO List

- [x] Website for setup, VLM Agents, and leaderboard  
- [x] Code for demo generation, rendering, and evaluation  
- [ ] Release of full asset pack (10K+ objects)  
- [ ] Baseline models (ACT, Seer, InternVLA-M1, etc.)  
- [ ] Objaverse scaling pipeline integration  

---

## 📚 Citation

If you find this work useful, please cite:

```bibtex
@inproceedings{gao2025genmanip,
  title={GenManip: LLM-driven Simulation for Generalizable Instruction-Following Manipulation},
  author={Gao, Ning and Chen, Yilun and Yang, Shuai and Chen, Xinyi and Tian, Yang and Li, Hao and Huang, Haifeng and Wang, Hanqing and Wang, Tai and Pang, Jiangmiao},
  booktitle={CVPR},
  year={2025}
}
