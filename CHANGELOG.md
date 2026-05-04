# Changelog

All notable changes to voice-input.
## [unreleased]
### 2026-05-04
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`34fa533`](https://github.com/artur-arc/voice-input/commit/34fa53364a0d5f453c1469f021245516e0bce3c2) Extend model support on Windows

## v1.0.41 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`2866a64`](https://github.com/artur-arc/voice-input/commit/2866a64a2d34acb85e91d4118298e75ac33c48a1) Release v1.0.41
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`ccf2f29`](https://github.com/artur-arc/voice-input/commit/ccf2f295d7c6022857897b8d7097af7a0a6841d7) Remove redundant tray instance killing in setup.py

## v1.0.40 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`eedcdb9`](https://github.com/artur-arc/voice-input/commit/eedcdb9bc4c727fe66eb6d548ae44afca7b637cf) Release v1.0.40
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`520b7d7`](https://github.com/artur-arc/voice-input/commit/520b7d73a8d6d5495c3ebb40252c10d327e40666) Enable verbose mode for CT2 library

## v1.0.39 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`0a7c9d8`](https://github.com/artur-arc/voice-input/commit/0a7c9d810ebf7d467949509b952b887c2682df7c) Release v1.0.39
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`c7cea41`](https://github.com/artur-arc/voice-input/commit/c7cea4110ab19bc6676f22077706c22d563b2bbc) Pin ctranslate2<4.7, auto-downgrade if 4.7+ detected

## v1.0.38 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`7cf1a74`](https://github.com/artur-arc/voice-input/commit/7cf1a74ccb503bf79a335babd54ceb9a8fce9725) Release v1.0.38
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`3eb2fdb`](https://github.com/artur-arc/voice-input/commit/3eb2fdb50ff1f30a4a3170235e0a9be76a9fb6ed) Probe float16 first; remove incorrect size-based stale check
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`dc61da9`](https://github.com/artur-arc/voice-input/commit/dc61da922b4452d08433a366988aac261f9b67b6) Show 'waiting for model' notification only once

## v1.0.37 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`5782a35`](https://github.com/artur-arc/voice-input/commit/5782a35080e1864a7d262d58b0c2db0d0ce5b1b2) Release v1.0.37
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`5337d27`](https://github.com/artur-arc/voice-input/commit/5337d27400f73b51990d7524339ae85ca452ea25) Ensure logging setup runs only once
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`1991136`](https://github.com/artur-arc/voice-input/commit/199113617645d955634f65ee82b9687f8324d1f7) Kill tray before model ops; show loading status in icon title

## v1.0.36 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`cf1eda7`](https://github.com/artur-arc/voice-input/commit/cf1eda724b2a13453722b395b6384e572fe7cad4) Release v1.0.36
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`ad915d5`](https://github.com/artur-arc/voice-input/commit/ad915d5ed5640908014d1a10c15245501d899aa3) Increase int8 probe timeout from 60s to 300s

## v1.0.35 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`b5ca27f`](https://github.com/artur-arc/voice-input/commit/b5ca27f3abdcd4a1d5aa7ddffe8db7fd5fa0af01) Release v1.0.35
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`97f4c87`](https://github.com/artur-arc/voice-input/commit/97f4c87fc01da6703f2882ec1894058c9b23562f) Kill existing tray instance before launching fresh one
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`ed9ff53`](https://github.com/artur-arc/voice-input/commit/ed9ff53884286d1aba7fe2499882b79fc1bd0d5c) Re-download model when model.bin is missing or oversized
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`9e0e4bd`](https://github.com/artur-arc/voice-input/commit/9e0e4bd5d72462901e3eff50f0ca6d88db63d277) Release v1.0.34
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`2c80315`](https://github.com/artur-arc/voice-input/commit/2c80315ad11aaf1b3d24a2bed475f0202f26f4bb) Delete mlx-whisper model cache on macOS uninstall
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`884854a`](https://github.com/artur-arc/voice-input/commit/884854a04a443d74441a44f39aa4402901121758) Delete model cache and app folder on uninstall
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`9427edb`](https://github.com/artur-arc/voice-input/commit/9427edb35e4c9ebd0f22708d0d9e1b58b4121068) Auto-detect and replace stale ctranslate2 v3 format models

## v1.0.33 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`e76ec6e`](https://github.com/artur-arc/voice-input/commit/e76ec6edc78b12826a63d34a779cbf7a77c0032e) Release v1.0.33
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`0283a32`](https://github.com/artur-arc/voice-input/commit/0283a32567b7804702b15c36a37cb567cb8199ea) Add worker diagnostics, improve 0xC0000005 guidance

## v1.0.31 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`fc6d3d5`](https://github.com/artur-arc/voice-input/commit/fc6d3d57275a5cd710a5b298dbdb18f1c043c23b) Release v1.0.31
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`d2b4079`](https://github.com/artur-arc/voice-input/commit/d2b40792e3a0c8a8ac7268e1c17cee09a81e55c1) Validate model.bin size to prevent ctranslate2

## v1.0.30 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`839041e`](https://github.com/artur-arc/voice-input/commit/839041e1e761f06ab86b393ce8d3800dcb5abbcc) Release v1.0.30
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`22ce7f9`](https://github.com/artur-arc/voice-input/commit/22ce7f9b0af214c3ad01c2bb4a9421b9516da857) Isolate ctranslate2 in subprocess to prevent

## v1.0.29 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`3dd867c`](https://github.com/artur-arc/voice-input/commit/3dd867c60b45713331c6aac4c6cf53b11219838c) Release v1.0.29
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`d9baed0`](https://github.com/artur-arc/voice-input/commit/d9baed0a74c88e6c0a3ee8bb1a4432f970902628) Update feedback and transcription handling

## v1.0.28 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`8eec775`](https://github.com/artur-arc/voice-input/commit/8eec7756f119c427eb0b29684b913b0adacef945) Release v1.0.28

## v1.0.27 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`081bcf8`](https://github.com/artur-arc/voice-input/commit/081bcf8ae11f47f4aab381315d92253b52a69ac0) Release v1.0.27
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`5993d80`](https://github.com/artur-arc/voice-input/commit/5993d80864a1d42fbabb92da8b3f083536ab2a38) Update Windows paste implementation to use
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`8ed4d4a`](https://github.com/artur-arc/voice-input/commit/8ed4d4adfc10cd73c2cff10500bccd138f0e70cf) Restrict Python version to 3.11-3.12 for compatibility

## v1.0.26 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`eea0c31`](https://github.com/artur-arc/voice-input/commit/eea0c31c1b8fede0a6685640bef0ec48bd460e16) Release v1.0.26
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`beebb11`](https://github.com/artur-arc/voice-input/commit/beebb1126814239d2c371f458d1af878b030b4bb) Update clipboard handling for Windows
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`2595f2f`](https://github.com/artur-arc/voice-input/commit/2595f2fe4d71f353e7962afb355e4c96f3a1d7b7) Cache working compute_type, add OMP_NUM_THREADS=1

## v1.0.25 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`e39d00b`](https://github.com/artur-arc/voice-input/commit/e39d00bcb010d1e988113241c36dfff8ba218815) Release v1.0.25
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`c10aa35`](https://github.com/artur-arc/voice-input/commit/c10aa35b860d16065db675368aa493070c72535e) Set CT2_FORCE_CPU_ISA=GENERIC before ctranslate2 import
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`8800fac`](https://github.com/artur-arc/voice-input/commit/8800fac230f62d9df112cf5a3857745649e05b68) Reduce int8 timeout to 60s, add sound on model ready

## v1.0.24 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`c00603c`](https://github.com/artur-arc/voice-input/commit/c00603c4f7cc3834976df9f162fa9759a9300b3c) Release v1.0.24
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`d254a5a`](https://github.com/artur-arc/voice-input/commit/d254a5adfa2bcd5637ffa9c371dc3059e5b185cf) Fallback to float32 if int8 times out or fails
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`dee4626`](https://github.com/artur-arc/voice-input/commit/dee46269417e431319c7404e4d78bc76507f1d70) Type hint plyer import for Windows-only
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`7f25fdc`](https://github.com/artur-arc/voice-input/commit/7f25fdc7c0b5b2a03002c311f9b424db236b583b) Prevent multiple simultaneous instances via Windows mutex
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`b7003af`](https://github.com/artur-arc/voice-input/commit/b7003af84a04a5cb18f724797f54bf98127faa8b) Fail fast if model not cached, add 300s load timeout

## v1.0.23 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`e7fbbcb`](https://github.com/artur-arc/voice-input/commit/e7fbbcb4f2ba34cc65c83aed841b561fa2c44e89) Release v1.0.23
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`5145d7a`](https://github.com/artur-arc/voice-input/commit/5145d7a606e714534b26a887be11fdf277188789) Cache HuggingFace models in user directory
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`493ef62`](https://github.com/artur-arc/voice-input/commit/493ef625f65d712883b808703dea3cf34c28aa29) Ensure unique download script file for parallel installs

## v1.0.22 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`134d0e9`](https://github.com/artur-arc/voice-input/commit/134d0e9a1147c37406a85dbe6272a7e9528ae138) Release v1.0.22
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`c5680e2`](https://github.com/artur-arc/voice-input/commit/c5680e2c3a1a92fd50ef9f5fff8df7749da9bb0a) Prioritize cached model for faster-whisper

## v1.0.21 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`3319c0e`](https://github.com/artur-arc/voice-input/commit/3319c0e26ae8fc2eb7c7b6d02b67b565bf74bdea) Release v1.0.21
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`3d3661b`](https://github.com/artur-arc/voice-input/commit/3d3661b12faf3ca32407543733f1aeaac49d6ebf) Skip voice input download if setup.py exists

## v1.0.20 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`9610129`](https://github.com/artur-arc/voice-input/commit/961012997de971a90330f711a067de60a2263f2e) Release v1.0.20
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`0eabed8`](https://github.com/artur-arc/voice-input/commit/0eabed8f2f9e577600cffd51fc6fee7ca97f5707) Detect model based on RAM

## v1.0.19 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`f229002`](https://github.com/artur-arc/voice-input/commit/f229002942c6141c6968b5977c91af7141a2816c) Release v1.0.19
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`5dd4849`](https://github.com/artur-arc/voice-input/commit/5dd4849e54f969702707751d8128301d09d6a96b) Add model loading readiness
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`e5b8d8d`](https://github.com/artur-arc/voice-input/commit/e5b8d8ddf4fc94f845794302c65c6c8fac59bf5d) Update installation instructions for Windows and macOS

## v1.0.18 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`459c9f9`](https://github.com/artur-arc/voice-input/commit/459c9f9f191fb526f7fc525e2a3873067b68d3be) Release v1.0.18
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`b299a66`](https://github.com/artur-arc/voice-input/commit/b299a66d46f8718039efc9a1bd0e561bad15a3e5) Ensure log file handler flushes after each record

## v1.0.17 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`0d328a2`](https://github.com/artur-arc/voice-input/commit/0d328a210f08dfaa193954fe4ab64bae50e49199) Release v1.0.17

## v1.0.16 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`d1520e2`](https://github.com/artur-arc/voice-input/commit/d1520e2fe9dd7dbafe7023e1a7e45abd66973ae4) Release v1.0.16

## v1.0.15 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`6f46359`](https://github.com/artur-arc/voice-input/commit/6f46359b24360423d0aa96ff0dbd798914223541) Release v1.0.15
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`f3d46e3`](https://github.com/artur-arc/voice-input/commit/f3d46e3c0901d722f4852c55d9a81cc1033147cc) Remove model warm-up step

## v1.0.14 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`39238c0`](https://github.com/artur-arc/voice-input/commit/39238c0aefc2dd21c829c01d1e0b9deeb8745419) Release v1.0.14
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`8aa2678`](https://github.com/artur-arc/voice-input/commit/8aa2678726253a68d0a5ac17d99d36ff9fc78a82) Redirect voice input output to log file
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`bf5abe0`](https://github.com/artur-arc/voice-input/commit/bf5abe07ab2ceb3d4a0982e34a63b760a52830c3) Ensure logging works on Windows

## v1.0.13 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`5c8268d`](https://github.com/artur-arc/voice-input/commit/5c8268d52b2a08d09d85e6231d2a945b107f9cd2) Release v1.0.13
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`543d181`](https://github.com/artur-arc/voice-input/commit/543d1815431d96c433f7e7ed2ab5d44c703ba99a) Handle exceptions and log errors during
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`3157580`](https://github.com/artur-arc/voice-input/commit/3157580649a4ab7312ca976784edddc456381306) Simplify package installation logic

## v1.0.12 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`1334d11`](https://github.com/artur-arc/voice-input/commit/1334d111c1e2636929e99bfe696f21afe49b87f1) Release v1.0.12
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`36f5571`](https://github.com/artur-arc/voice-input/commit/36f557113095bcaaee6a955a20bcec601c3906a4) Update package installation messages for windows
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`3f35770`](https://github.com/artur-arc/voice-input/commit/3f3577077e329e91f098d9389be7e58393ad4ce3) Replace package check with import-based probe

## v1.0.11 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`69bc831`](https://github.com/artur-arc/voice-input/commit/69bc831aa14ca5c7a5732f808c5ff88948ff1ef7) Release v1.0.11

## v1.0.10 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`beacae9`](https://github.com/artur-arc/voice-input/commit/beacae949a2d294cf8be591fa933e5f987492908) Release v1.0.10

## v1.0.9 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`cc57162`](https://github.com/artur-arc/voice-input/commit/cc571620ed92ec6306cd8b5a6836800496033ef0) Release v1.0.9

## v1.0.8 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`8d0a5e0`](https://github.com/artur-arc/voice-input/commit/8d0a5e06c4b4dd458ded612511bc445e129db673) Release v1.0.8
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`e463240`](https://github.com/artur-arc/voice-input/commit/e4632403906a7907010883dbb032dd84f5865631) Suppress HF Hub warnings during model download
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`432fc73`](https://github.com/artur-arc/voice-input/commit/432fc737b077cf154262de7589f70b58e8655fc4) Bump Python version to 3.13.3

## v1.0.7 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`51941e3`](https://github.com/artur-arc/voice-input/commit/51941e399670e6c4fe0937d8649cc2f7b7f77f56) Release v1.0.7
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`8b80088`](https://github.com/artur-arc/voice-input/commit/8b80088e7f6ab1b950678c69c10cadc9c00c1f77) Update Russian translation settings

## v1.0.6 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`872f7fc`](https://github.com/artur-arc/voice-input/commit/872f7fc6eba799a4efdd5402bdb0997babc8e73c) Release v1.0.6
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`ef152ba`](https://github.com/artur-arc/voice-input/commit/ef152bae41da7bf8a737f8ddee6b49239de27083) Use python -m pip for package installation
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`dedc358`](https://github.com/artur-arc/voice-input/commit/dedc358863a1792d42e0a766bf533c7ba5b1cf78) Simplify path refresh logic

## v1.0.5 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`25254a3`](https://github.com/artur-arc/voice-input/commit/25254a30da95392903c3da08d54f2cac0e36c184) Release v1.0.5

## v1.0.4 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`90dba1f`](https://github.com/artur-arc/voice-input/commit/90dba1fdb2b950c749f426144c9e5e9e4cf71055) Release v1.0.4

## v1.0.3 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`5bda180`](https://github.com/artur-arc/voice-input/commit/5bda1802cc69d5bf6fbf6f3ec464e85caa40c04a) Release v1.0.3

## v1.0.2 — 2026-05-03
### 2026-05-03
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`8fd92a5`](https://github.com/artur-arc/voice-input/commit/8fd92a55365e5916b1cf219554002da41e26045d) Release v1.0.2
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`bb24cae`](https://github.com/artur-arc/voice-input/commit/bb24cae5bdfdeab40fe8f1d713617f0e082e8f4f) Update updater to handle GitHub releases and
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`c0c92f1`](https://github.com/artur-arc/voice-input/commit/c0c92f132c01ccf71a3cfa6a7418c2125b5c4553) Update installer to support Windows
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`304d400`](https://github.com/artur-arc/voice-input/commit/304d400bb75da5805ea7a2f764588582eb7719bf) Add Windows installer and requirements
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`8689fca`](https://github.com/artur-arc/voice-input/commit/8689fca27458469d39053b72154f791e4e9277bc) Update logging for restart and update operations
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`2b52185`](https://github.com/artur-arc/voice-input/commit/2b52185d1afe5503853a3e5710ceef328d7aea26) Wait for services to start before completing
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`328df34`](https://github.com/artur-arc/voice-input/commit/328df3446ca9987b48fbe0997776935dd5421b97) Update macOS permissions and structure
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`a2cc3f4`](https://github.com/artur-arc/voice-input/commit/a2cc3f445a709bb1169feb564fbd2f9771b8bbc4) Update permission check for macOS voice input
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`0d1ee96`](https://github.com/artur-arc/voice-input/commit/0d1ee96ed9ca5a110be10c949d28e77eee6e0ded) Add permissions menu and checks for microphone, input monitoring,
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`d607fba`](https://github.com/artur-arc/voice-input/commit/d607fba56c1b55919077605bf657310e114c09ac) Update file URLs and add download instructions
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`a1e6316`](https://github.com/artur-arc/voice-input/commit/a1e6316eb20f1cab7d6b2fadc9e96cf2cdaee787) Add uninstall option
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`c4af4fd`](https://github.com/artur-arc/voice-input/commit/c4af4fd0097694d15982db57f82ce70479fc63fe) Increment default mode index
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`8fa8150`](https://github.com/artur-arc/voice-input/commit/8fa81500993aa8f53a23c0d357ea3dd4cd154686) Update auto-start status and hotkey description
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`f882f22`](https://github.com/artur-arc/voice-input/commit/f882f22b9460272d114ced17d08f86b12a6c5d9d) Refactor menu bar and service launchd agents
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`916e3db`](https://github.com/artur-arc/voice-input/commit/916e3db0d8ff0a24e5f02ad3fc04b00127f85cb9) Handle config file changes gracefully
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`81422a6`](https://github.com/artur-arc/voice-input/commit/81422a6d8c0292e6fb9c9d23d1dc9f75a4e625bd) Update README and config for improved text
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`e5445f4`](https://github.com/artur-arc/voice-input/commit/e5445f4b6380299d4b9c0bdff3c056b71089c3f1) Add microphone selection instructions
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`e8e6289`](https://github.com/artur-arc/voice-input/commit/e8e6289f31dcdff46738b40e11742773187e7456) Add dynamic microphone selection functionality
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`3e4080d`](https://github.com/artur-arc/voice-input/commit/3e4080d30ced9eb8ea64c08416a21aaed7dfad08) Add logging and improve error handling
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`e10cd62`](https://github.com/artur-arc/voice-input/commit/e10cd628163e4d20570c5dffc895fb24008a17a7) Add logging and error handling
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`9ecf882`](https://github.com/artur-arc/voice-input/commit/9ecf88207002c7d8e69a20483f23739aec033743) Update install command link
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`0a73655`](https://github.com/artur-arc/voice-input/commit/0a73655a09096db18f63a81876881982e87c7fe2) Update entry point to main.py
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`97b2c75`](https://github.com/artur-arc/voice-input/commit/97b2c75abd2f2b51cf7942c1d20bb6fe5b21bc9a) Add permissions and language mode instructions
- ![chore](https://img.shields.io/badge/chore-cfd3d7?style=flat-square) [`d33b130`](https://github.com/artur-arc/voice-input/commit/d33b13051a7e48506c78d7fc564070e26091d83b) Update installation instructions and mode descriptions
- ![fix](https://img.shields.io/badge/fix-d73a4a?style=flat-square) [`76c3f12`](https://github.com/artur-arc/voice-input/commit/76c3f12642ee905f1fcd4e53a342591de580a028) Correct mode and config for English-English transcriptions
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`cb9c2f8`](https://github.com/artur-arc/voice-input/commit/cb9c2f86cbcb207fee0acc1f9c2e66aa0e242120) Add voice input installer script
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`57a5321`](https://github.com/artur-arc/voice-input/commit/57a532193b123d54186ab1e05f861a468b0e24d1) Update documentation and structure
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`bf01ee7`](https://github.com/artur-arc/voice-input/commit/bf01ee7794bfa26604af030c1b78b04113a15b30) Simplify and streamline installation process
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`5163c63`](https://github.com/artur-arc/voice-input/commit/5163c63542729da8477a3240f5de45507ae64d48) Add accessibility binary retrieval for UI updates
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`fd4b899`](https://github.com/artur-arc/voice-input/commit/fd4b89947ab935f322c006256647fa59c9769e38) Implement text paste using CGEvent
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`138a1d3`](https://github.com/artur-arc/voice-input/commit/138a1d354fc7363d47d250a3db33992a50d07fd8) Introduce text cleanup functionality with ollama model
### 2026-05-02
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`8eb20db`](https://github.com/artur-arc/voice-input/commit/8eb20db8cbd6db154d11dc651a56d1647b32ebd7) Move project one level up, reorganize src layout
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`fabbdd6`](https://github.com/artur-arc/voice-input/commit/fabbdd68d728c7a263df8d2a74d8950a25c4d78e) Update mode configuration and labels
- ![refactor](https://img.shields.io/badge/refactor-e4e669?style=flat-square) [`59c2248`](https://github.com/artur-arc/voice-input/commit/59c2248fbd5a4f08989e1d508fd970afbe20e30e) Preserve clipboard state during voice
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`9bb16e0`](https://github.com/artur-arc/voice-input/commit/9bb16e021139897ad3c79bdf60683fd56b1664c0) Add README.md and .markdownlint.json for better
- ![feat](https://img.shields.io/badge/feat-0075ca?style=flat-square) [`c798f82`](https://github.com/artur-arc/voice-input/commit/c798f8204bfe9289eaa75b9a44da5234253b197d) Add voice input functionality with hotkeys and


