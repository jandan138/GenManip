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

**GenManip** is a large-scale simulation and evaluation platform for **generalist robotic manipulation policies** under diverse and realistic **instruction-following scenarios**.

Built on [NVIDIA Isaac Sim](https://developer.nvidia.com/isaac-sim), **GenManip** enables:
- 🧠 **LLM-driven task generation** via a novel **Task-oriented Scene Graph (ToSG)**  
- 🔬 **200 curated evaluation scenarios** for both modular and end-to-end policy benchmarking  
- 🧱 A scalable asset pool with **10,000+ rigid** and **100+ articulated** objects with multimodal annotations  
- 🧭 Evaluation of **spatial**, **appearance**, **commonsense**, and **long-horizon reasoning** abilities  

---

## 🚀 Recent Highlights

### 🔹 Oct 2025 — Data & Evaluation Release
The **data synthesis pipeline** and **evaluation toolkit** for generalizable pick-and-place tasks are now available.

### 🔹 Aug 2025 — IROS 2025 Challenge Integration  
GenManip serves as the **core simulation backbone** for the **IROS 2025 Challenge: Vision-Language Manipulation in Open Tabletop Environments**.

- Generated **55K+ generalizable pick-and-place tasks** across ~14K objects using the ALOHA platform  
- Released **10 expert-designed post-training tasks** for dual-arm manipulation  
- Provided diverse **pre-training data** with randomized objects, scenes, and language instructions to promote **cross-domain generalization**

📌 **Challenge Registration:**  
[https://eval.ai/web/challenges/challenge-page/2626/overview](https://eval.ai/web/challenges/challenge-page/2626/overview)

<p align="center">
  <img src="readme_assets/iros-teaser.jpg" width="80%" alt="IROS 2025 Teaser"/>
</p>

---

## 📂 Dataset Access

| Type | Description | Link |
|------|--------------|------|
| **Pre-training Data** | Dual-arm generalizable pick-and-place (55K+ samples) | [Hugging Face](https://huggingface.co/datasets/InternRobotics/IROS-2025-Challenge-Manip/tree/main) |
| **Post-training Data** | Dual-arm manipulation, 10 benchmark tasks | [Hugging Face](https://huggingface.co/datasets/InternRobotics/IROS-2025-Challenge-Manip/tree/main) |

<video src="readme_assets/scaling_data.mp4" controls width="600"></video>

**Additional Resources**
- The **GenManip Benchmark** will be merged into [InternManip](https://github.com/InternRobotics/InternManip)  
- Datasets are also included in **[InternData-M1](https://huggingface.co/datasets/InternRobotics/InternData-M1)** — a large-scale embodied robotics dataset with ~250K demonstrations and rich annotations (2D/3D boxes, trajectories, grasps, masks)  
- Conversion to **LeRobot** format is ongoing; all data has been generated and will be fully available soon  
- Scaling data for **long-horizon, multi-stage manipulation** is in progress 🚀  

---

## ✨ Key Features

| Feature | Description |
| -------- | ------------ |
| 🎯 **ToSG-based Task Synthesis** | Graph-based semantic representation for generating compositional tasks |
| 🖼️ **Photorealistic Simulation** | RTX ray-traced rendering with physically accurate dynamics |
| 📊 **Benchmark Suite** | 200+ diverse tasks with human-in-the-loop annotation refinement |
| 🧪 **Evaluation Toolkit** | Supports SR, SPL, ablation studies, and generalization diagnostics |

---

## 🧩 TODO List

- [x] Website, documentation, and leaderboard  
- [x] Code release for task synthesis, rendering, and evaluation  
- [ ] Full GenManip asset pack (10K+ objects)  
- [ ] Baseline model implementations (ACT, Seer, InternVLA-M1, etc.)  
- [ ] Objaverse scaling pipeline  

---

## 📚 Citation

If you find our work useful, please cite:

```bibtex
@inproceedings{gao2025genmanip,
  title={GenManip: LLM-driven Simulation for Generalizable Instruction-Following Manipulation},
  author={Gao, Ning and Chen, Yilun and Yang, Shuai and Chen, Xinyi and Tian, Yang and Li, Hao and Huang, Haifeng and Wang, Hanqing and Wang, Tai and Pang, Jiangmiao},
  booktitle={CVPR},
  year={2025}
}
