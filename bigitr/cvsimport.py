#
# Copyright 2012 SAS Institute
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import os
import time

from bigitr import cvs
from bigitr import errhandler
from bigitr import git
from bigitr import gitmerge
from bigitr import ignore
from bigitr import util

class Importer(object):
    def __init__(self, ctx):
        self.ctx = ctx
        self.err = errhandler.Errors(ctx)

    def importAll(self):
        for repository in self.ctx.getRepositories():
            Git = git.Git(self.ctx, repository)
            self.importBranches(repository, Git)

    def importBranches(self, repository, Git, requestedBranch=None):
        onerror = self.ctx.getImportError()
        for cvsbranch, gitbranch in self.ctx.getImportBranchMaps(repository):
            if requestedBranch is None or cvsbranch == requestedBranch:
                CVS = cvs.CVS(self.ctx, repository, cvsbranch)
                try:
                    self.importcvs(repository, Git, CVS, cvsbranch, gitbranch)
                except Exception as e:
                    self.err(repository, onerror)

    @util.saveDir
    def importcvs(self, repository, Git, CVS, cvsbranch, gitbranch):
        gitDir = self.ctx.getGitDir()
        repoName = self.ctx.getRepositoryName(repository)
        repoDir = '/'.join((gitDir, repoName))
        skeleton = self.ctx.getSkeleton(repository)
        exportDir = self.ctx.getCVSExportDir(repository)

        if os.path.exists(exportDir):
            util.removeRecursive(exportDir)
        os.makedirs(exportDir)
        os.chdir(os.path.dirname(exportDir))
        CVS.export(os.path.basename(exportDir))
        cvsignore = ignore.Ignore(Git.log, exportDir + '/.cvsignore')
        exportedFiles = util.listFiles(exportDir)
        if not exportedFiles:
            raise RuntimeError("CVS branch '%s' for location '%s' contains no files"
                               %(CVS.branch, CVS.location))
        os.chdir(exportDir)

        Git.initializeGitRepository()

        os.chdir(repoDir)
        addSkeleton = False
        branches = Git.branches()
        if gitbranch not in branches:
            if 'remotes/origin/' + gitbranch in branches:
                # check out existing remote branch
                Git.checkoutTracking(gitbranch)
            else:
                # check out a new "orphan" branch
                Git.checkoutNewImportBranch(gitbranch)
                addSkeleton = True
        else:
            if Git.branch() != gitbranch:
                Git.checkout(gitbranch)
            Git.fetch()
            Git.mergeFastForward('origin/' + gitbranch)

        # clean up after any garbage left over from previous runs so
        # that we can change branches
        Git.pristine()

        gitFiles = Git.listContentFiles()
        gitFiles = sorted(list(cvsignore.filter(set(gitFiles))))
        for filename in gitFiles:
            os.remove(filename)

        os.chdir(gitDir)

        util.copyFiles(exportDir, repoDir, exportedFiles)

        if addSkeleton:
            if skeleton:
                skelFiles = util.listFiles(skeleton)
                util.copyFiles(skeleton, repoDir, skelFiles)

        os.chdir(repoDir)
        Git.runImpPreHooks(gitbranch)
        if Git.status():
            # there is some change to commit
            Git.infoStatus()
            Git.infoDiff()
            # store Git.log.lastOutput() to email after successful push
            Git.addAll()

        # Git.addAll() will have regularized line ending differences,
        # and in case that is the only change, we need to check again
        # on status
        if Git.status():
            # FIXME: try to create a commit message that includes all
            # the CVS commit messages since the previous commit, de-duplicated
            Git.commit('import from CVS as of %s' %time.asctime())
            Git.push('origin', gitbranch, gitbranch)
            Git.runImpPostHooks(gitbranch)

        merger = gitmerge.Merger(self.ctx)
        merger.mergeFrom(repository, Git, gitbranch)
