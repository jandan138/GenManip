# EBench (Exciting Benchmark)

![EBenchVersion](https://img.shields.io/badge/EBench-0.1.0--260128--alpha-blue) 
![Dataset](https://img.shields.io/badge/dataset--commit-2f6cd97-orange)

This directory contains the task configuration files for **EBench**. The benchmark consists of a diverse set of robotic manipulation tasks designed to evaluate Vision-Language Action (VLA) models, ranging from **pick-and-place** to complex **long-horizon** and **dexterous/precise** tasks.

## Dataset Preparation

The recommended benchmark version is `v0.1.0-260128-alpha`. Clone and check out the matching branch:
```bash
git clone https://gitee.pjlab.org.cn/L2/SimPlatform/EBench.git
cd EBench
git checkout v0.1.0-260128-alpha
```
The dataset commit pinned in the badge above is `2f6cd97`.

## Asset Acceptance

External assets should not be treated as EBench-ready just because a USD loads
once in Isaac. LabUtopia uses an evidence-gated asset acceptance workflow that
checks package inputs, USD composition, material closure, physics stability,
articulation semantics, task runtime, evaluator-camera render evidence, and
Lift2-style evaluator contracts separately.

Canonical SOP:

```text
docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md
```

Manifest field guide:

```text
docs/labutopia_lab_poc/evidence_manifests/README.md
```

Key boundary: a local task/runtime contract pass is not policy success or an
official leaderboard result. A single material dependency mirror, such as
Aluminum, is not full native material closure unless every remaining fallback
surface is also closed or explicitly waived.
