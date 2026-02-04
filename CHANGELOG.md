# [0.4.0](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/compare/v0.3.1...v0.4.0) (2026-02-04)


### Features

* **client:** add optional guid parameter to user group retrieval ([f3154b7](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/f3154b72efabb3abeb1821414bd584a9999c578d))

## [0.3.1](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/compare/v0.3.0...v0.3.1) (2026-02-03)


### Bug Fixes

* allow name in ExecutableStatus to be optional ([ae15e8e](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/ae15e8ef596aef585321ce295f5adff386addf1c))
* oauth2 endpoints ([4023a0e](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/4023a0e93faf51eda1f37797bd04c5f1ccaa4629))

# [0.3.0](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/compare/v0.2.4...v0.3.0) (2026-01-28)


### Bug Fixes

* add list_dependencies method for network ([6385493](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/63854934714e22ee5346bc164d59838abd9299fd))
* **client:** increases client timeout to 60 secs ([68d6964](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/68d69647a2514fd4e43e7ec10e4ef55b0d4fecfc))
* ensure 'Bearer ' prefix in Authorization header and handle missing keys in config tree response ([a091b03](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/a091b0317f19336a2624154507058dc09d23e350))
* fixed put_key_in_rev method as its expects a payload ([153af2d](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/153af2d446315b85e88ec024f1a9b3176c5e14de))
* **package:** add the default Scheme for HTTPGet Probe ([f3ff7e9](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/f3ff7e9a56d4edcb406b4025fddeeea3d062bf5b))
* **package:** handle single string command ([e129a48](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/e129a48458da43bafc2830925d09e5b6dfac55f9))
* refactored handle server error method ([40b2f0c](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/40b2f0c34074e7181c510cb8a68864ba25efbaa2))
* remove decorator from get_key_in_revision and return raw response ([#21](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/issues/21)) ([d024672](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/d024672bc8fc9ebd88c1974051aacaa7503eb782))
* remove duplicate default value in DeploymentROSNetwork model ([0da7b43](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/0da7b43674c686377affd226529ef4b6c683d7e0))
* **user:** handle ServiceAccount in get_myself ([fcf9b58](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/fcf9b58ae142b03dc64f4b1d58c316de08161a37))


### Features

* add BulkRoleBindingCreate and BulkRoleBindingUpdate models, and update role and role binding methods to support dict input ([9596f37](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/9596f372e58969f0553a50ba33157db2c2334f8c))
* add field validator for absolute paths in DeploymentVolume and clean up imports in models ([91d2e4a](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/91d2e4af9537093ef292cbb5d232c39ec752bcd7))
* add field validators to handle empty dicts in DockerSpec and PackageSpec ([87ecd90](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/87ecd90331a045b048958e1a2e92a28821079996))
* add override decorator to list_dependencies method in multiple models ([c625d1b](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/c625d1b2c00f124c5646421c544ee44a8c853cc3))
* add run_as_bash field to Executable model and prepend bash to command if set ([cba7415](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/cba74155774e0e8aa9b175ba948be4110fc66b26))
* add SecretCreate model and update create_secret methods to use it, enhancing secret management ([e4b0247](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/e4b024775e2e4bc48a1c40a4c8ea1007b22a39e2))
* add SecretDepends model and update DockerSpec to use PullSecret ([51226aa](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/51226aa0ed2ab004bc5b8e61ed97cbeafac0c2a4))
* add ServiceAccount models and API methods for management ([f0cebdc](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/f0cebdcc74e74c07e9dd02412ade0461dfaab8d6))
* add user and role management methods to AsyncClient and Client, and introduce OAuth2UpdateURI model ([50e4b01](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/50e4b015472206126570796fd5a7a99921e44ff6))
* enhance authorization header handling and update Depends model aliases ([eae39bd](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/eae39bd3d4ef0eb0ab345f057c9c6416be3c4489))
* handle empty dependencies in Package model by returning None ([fc23817](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/fc2381700db8378396f12f3fbab423a0e7c594d9))
* implement ServiceAccount management methods and improve pagination handling ([b988ac4](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/b988ac46dc3a60ac5d2ba6e93b226de8bc37bd99))
* implement user management methods including add, update, and delete functionalities ([c86c6fd](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/c86c6fdb1356ce145347c7f705f970cc1df84d61))
* introduce get subject method ([33a58a6](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/33a58a6843d74708af9241059848c3f2eaba1dd2))
* modify command field in Executable model to accept string or list of strings ([c52007d](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/c52007dcf7d58b82b4c8a95f5e0e333afa0655ab))
* **rbac:** add rbac models ([510b8b8](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/510b8b8adbdfb822600666dc159666197fd44847))
* remove unused imports from network and utils models ([8208547](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/82085474ece593897068b4f3cef9c4c6fe4a4da5))
* reorganize model imports for improved structure and clarity ([e137f43](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/e137f434f74d99495cdc3fe6f3143512e385b426))
* set default factories for Features models in Project ([66b2da2](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/66b2da2b34cd2ef48d0863bd2ffb9d29bdd25177))
* set default factory for Features in ProjectSpec ([42b40e4](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/42b40e4f50a9eb884aea986d14a19bef556fdf3b))
* update Depends model to use alias for name_or_guid field ([a901fe3](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/a901fe347a8d3a16b408598b4528c8a00fb7a235))
* update Depends model to use alias for name_or_guid field ([52eb22e](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/52eb22e404fa8c9db1fbb047bb79f801ac8db12b))
* update Features model to remove optional fields and ensure required structure ([c4ae092](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/c4ae092ad5623c56fd14e91aebfe5bbca25702e6))
* update FeaturesDockerCache model to correct data_directory assignment ([95bfe76](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/95bfe765c28bfb69bd93dc14edb43ca692987d6e))
* update PullSecret model to allow None for depends and handle empty dict ([b16f880](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/b16f88014cc8b47f1b7280b0260d83c7d81a49cb))
* update ServiceAccount kind to include lowercase variant ([5ea5cfb](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/5ea5cfbf085f2dfc2def49e363abc07262ee5ce7))
* update ServiceAccount token endpoints to use plural form ([e26f2d6](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/e26f2d66517641005175119916d70eccec63d095))

## [0.2.4](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/compare/v0.2.3...v0.2.4) (2025-12-30)


### Bug Fixes

* configtree fixes ([#23](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/issues/23)) ([9ea982a](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/9ea982ac0517359a185c05d8197d936b7f72cdac)), closes [#21](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/issues/21)

## [0.2.3](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/compare/v0.2.2...v0.2.3) (2025-10-26)


### Bug Fixes

* **config:** fixes local env api host ([2f746a3](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/2f746a352293af644670fae5507ae3df312a6880))

## [0.2.2](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/compare/v0.2.1...v0.2.2) (2025-10-21)


### Bug Fixes

* **config:** adds support for local v2-configtree env ([f30ec37](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/f30ec37bb465020c91d630d9784b861667b4f4cb))

## [0.2.1](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/compare/v0.2.0...v0.2.1) (2025-10-21)


### Bug Fixes

* **pydantic_source:** moved pydantic_source under rapyuta_io_sdk_v2 ([c71f32c](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/c71f32c2dbc068be69de03905d53d872ca6eb9dd))

# [0.2.0](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/compare/v0.1.0...v0.2.0) (2025-04-09)


### Features

* add Organization and User API ([b5eb50d](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/b5eb50d004c962ef66607fcab3b653ced5cc6c0a))

# [0.1.0](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/compare/v0.0.1...v0.1.0) (2024-12-13)


### Features

* add Client SDK for rapyuta.io v2 APIs ([9a459ce](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/9a459ce19b27e2a036cc4ec188fa6b21cca34e5c)), closes [AB#35882](https://github.com/AB/issues/35882)
* implements async client ([#5](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/issues/5)) ([2d74e3c](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/2d74e3c9de67ed51e9a2b2c70552a46879992cee))
* implements initial sync for v2 APIs ([#3](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/issues/3)) ([8eefdae](https://github.com/rapyuta-robotics/rapyuta-io-sdk-v2/commit/8eefdae4c9021c6f1cb9bcf0afe04aa51dea2c47))
