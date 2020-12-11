#
#    Copyright 2020, NTT Communications Corp.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#

import os
import datetime
import logging
import requests
import urllib3
from web3 import Web3
from google.cloud import storage, exceptions
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from solver import BaseSolver
from client_model import FILESERVER_ASSETS_PATH


LOGGER = logging.getLogger('common')

FUNCTIONS_URL = os.getenv("FUNCTIONS_URL", "")
FUNCTIONS_TOKEN = os.getenv("FUNCTIONS_TOKEN", "")


class Solver(BaseSolver):
    def __init__(self, contracts, account_id, operator_address):
        super().__init__(contracts, account_id, operator_address)
        self.uploader = Uploader()

    def notify_first_accept(self, view):
        if FUNCTIONS_URL:
            url = FUNCTIONS_URL
            view.vio.print('Solver として受付を開始しました。')
            view.vio.print(
                'チャレンジ結果は中継点( {} )にアップロードされます'.\
                format(url))
        else:
            view.vio.print('Solver用のURLが設定されていません。')

    def process_challenge(self, token_address, event):
        LOGGER.info('Solver: callback: %s', token_address)
        LOGGER.debug(event)
        try:
            task_id = event['args']['taskId']
            challenge_seeker = event['args']['from']
            LOGGER.info(
                'accepting task %s from seeker %s', task_id, challenge_seeker)
            if not self.accept_task(task_id):
                LOGGER.info('could not accept task %s', task_id)
                return
            LOGGER.info('accepted task %s', task_id)
        except Exception as err:
            LOGGER.exception(err)
            return

        data = ''
        try:
            try:
                download_url = self.upload_to_storage(token_address)
                url = Web3.toText(event['args']['data'])
            except:
                data = 'Challenge failed by solver side error'
                raise
            try:
                # return answer via webhook
                self.webhook(url, download_url, token_address)
            except Exception as err:
                data = 'cannot sendback result via webhook: ' + str(err)
                raise
        except Exception as err:
            LOGGER.exception(err)
            LOGGER.error('failed task %s', task_id)
        finally:
            self.finish_task(task_id, data)
            LOGGER.info('finished task %s', task_id)

    def upload_to_storage(self, cti_address):
        file_path = os.path.abspath('{}/{}'.format(
            FILESERVER_ASSETS_PATH, cti_address))
        url = self.uploader.upload_file(file_path)
        return url

class Uploader:
    def upload_file(self, upload_path):
        if not FUNCTIONS_URL:
            LOGGER.error('There are no settings for upload URL')
        else:
            headers = {
                'Authorization': 'Bearer {}'.format(FUNCTIONS_TOKEN),
                'Content-Type': 'application/json'}
            response = requests.post(
                FUNCTIONS_URL,
                data=open(upload_path, 'rb'),
                headers=headers)
            results = response.json()
            if 'result' in results:
                return results['result']
            LOGGER.error('File upload Error: %s', results['error'])
            return None
