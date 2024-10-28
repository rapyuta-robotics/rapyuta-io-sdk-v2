# -*- coding: utf-8 -*-
# Copyright 2024 Rapyuta Robotics
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Setting the name to "rio-cli" as the app name
# in order to keep the configuration file name
# consistent. The app name for the CLI as well
# as the SDK can be changed to "rio" in the future.
APP_NAME = "rio-cli"

LOGIN_API_PATH = "/user/login"
GET_USER_API_PATH = "/api/user/me/get"

STAGING_ENVIRONMENT_SUBDOMAIN = "apps.okd4v2.okd4beta.rapyuta.io"

NAMED_ENVIRONMENTS = ["ga", "qa", "dev"]
