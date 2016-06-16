import os.path
import traceback

from kvmagent import kvmagent
from zstacklib.utils import jsonobject
from zstacklib.utils import http
from zstacklib.utils import log
from zstacklib.utils import shell

logger = log.get_logger(__name__)

class AgentResponse(object):
    def __init__(self):
        self.totalCapacity = None
        self.availableCapacity = None
        self.success = None
        self.error = None

class ImageStorePlugin(kvmagent.KvmAgent):

    ZSTORE_PROTOSTR = "zstore://"
    ZSTORE_CLI_PATH = "/usr/local/zstack/imagestore/zstcli"
    UPLOAD_BIT_PATH = "/imagestore/upload"
    DOWNLOAD_BIT_PATH = "/imagestore/download"

    def start(self):
        http_server = kvmagent.get_http_server()
        http_server.register_async_uri(self.DOWNLOAD_BIT_PATH, self.download_from_imagestore)
        http_server.register_async_uri(self.UPLOAD_BIT_PATH, self.upload_to_imagestore)

        self.path = None

    def stop(self):
        pass

    def _get_disk_capacity(self):
        return linux.get_disk_capacity_by_df(self.path)

    def _get_image_reference(self, primaryStorageInstallPath):
        if not primaryStorageInstallPath.startswith(self.ZSTORE_PROTOSTR):
            raise kvmagent.KvmError('unexpected primary storage install path %s' % primaryStorageInstallPath)

        xs = primaryStorageInstallPath[len(self.ZSTORE_PROTOSTR):].split('/')
        if len(xs) != 2:
            raise kvmagent.KvmError('unexpected primary storage install path %s' % primaryStorageInstallPath)

        return xs[0], xs[1]

    @kvmagent.replyerror
    def upload_to_imagestore(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = AgentResponse()

        try:
            name, imgid = self._get_image_reference(cmd.primaryStorageInstallPath)
            cmdstr = '%s push %s' % (self.ZSTORE_CLI_PATH, name)
            logger.debug('pushing %s:%s to image store' % (name, imageid))
            shell.call(cmdstr)
            logger.debug('%s:%s pushed to image store' % (name, imageid))
        except kvmagent.KvmError as e:
            logger.warn(linux.get_exception_stacktrace())
            rsp.error = str(e)
            rsp.success = False

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def download_from_imagestore(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = AgentResponse()

        try:
            name, imgid = self._get_image_reference(cmd.primaryStorageInstallPath)
            cmdstr = '%s pull %s:%s' % (self.ZSTORE_CLI_PATH, name, imageid)
            logger.debug('pulling %s:%s from image store' % (name, imageid))
            shell.call(cmdstr)
            logger.debug('%s:%s pulled to local cache' % (name, imageid))
        except Exception as e:
            content = traceback.format_exc()
            logger.warn(content)
            err = "unable to download %s/%s, because %s" % (cmd.hostname, cmd.backupStorageInstallPath, str(e))
            rsp.error = err
            rsp.success = False

        rsp.totalCapacity, rsp.availableCapacity = self._get_disk_capacity()
        return jsonobject.dumps(rsp)
