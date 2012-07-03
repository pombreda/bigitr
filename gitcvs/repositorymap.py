#
# Read configuration files for mapping Git repositories to CVS locations
# for synchronization, including branch mappings.  Format is ini-style:
# [Path/To/Git/repository]
# gitroot = git@host # <gitroot>:<repositoryname>
# cvsroot = @servername:/path # pserver:<username> added dynamically
# cvspath = Path/To/CVS/directory
# skeleton = /path/to/skeleton
# branchfrom = <gitspec> # branch/tag/ref to branch from for new branch imports
# cvs.<branch> = <gitbranch> # CVS <branch> imports to "cvs-<gitbranch>" in Git
# git.<branch> = <cvsbranch> # Git <branch> exports to "<cvsbranch>" in CVS
# merge.<sourcebranch> = <targetbranch> <targetbranch> # Merge <sourcebranch> onto <targetbranch>(es)
# prefix.<branch> = <message> # prefix for CVS commit messages on <branch>
# email = <address> <address> # errors/warnings emailed to these addresses
# prehook.git = <command> <args> # hook to run in Git clone before committing to either Git or CVS
# prehook.imp.git = <command> <args> # hook to run in Git clone before committing to Git from CVS
# prehook.exp.git = <command> <args> # hook to run in Git clone before committing to CVS from Git
# prehook.cvs = <command> <args> # hook to run in CVS checkout before committing to CVS
# posthook.git = <command> <args> # hook to run in Git clone after committing to either Git or CVS
# posthook.imp.git = <command> <args> # hook to run in Git clone after committing to Git from CVS
# posthook.exp.git = <command> <args> # hook to run in Git clone after committing to CVS from Git
# posthook.cvs = <command> <args> # hook to run in CVS checkout after committing to CVS
# prehook.git.<branch> = <command> <args> # hook to run in Git clone before committing to Git branch <branch> or exporting it to CVS
# prehook.imp.git.<branch> = <command> <args> # hook to run in Git clone before committing to Git branch <branch> from CVS
# prehook.exp.git.<branch> = <command> <args> # hook to run in Git clone before committing to CVS from Git branch <branch>
# prehook.cvs.<branch> = <command> <args> # hook to run in CVS checkout before committing to CVS branch <branch>
# posthook.git.<branch> = <command> <args> # hook to run in Git clone after committing to Git branch <branch> or exporting it to CVS
# posthook.imp.git.<branch> = <command> <args> # hook to run in Git clone after committing to Git branch <branch> from CVS
# posthook.exp.git.<branch> = <command> <args> # hook to run in Git clone after committing to CVS from Git branch <branch>
# posthook.cvs.<branch> = <command> <args> # hook to run in CVS checkout after committing to CVS branch <branch>
#
# gitroot, cvsroot, email, skeleton, and hooks may be in a GLOBAL section,
# which will be overridden by any specific per-repository values.
#
# skeleton files are used only when creating a new cvs-* import branch.
# Note that changing the skeleton between creating cvs-* import branches
# will introduce merge conflicts when you merge cvs-* branches into
# Git development branches.  Any skeleton files other than .git* files
# will be included in the files exported from Git branches to CVS branches.
# The normal use of a skeleton is to introduce a .gitignore file that is
# different from .cvsignore and/or a .gitattributes file; if there is no
# skeleton and there is a top-level .cvsignore file, new branches will
# include the contents of .cvsignore as the initial .gitignore contents.
#
# For each git.<branch>, "export-<branch>" in Git is used to track what
# on <branch> has been exported to CVS.  This branch never has anything
# committed to it.  It only gets fast-forward merges from <branch>.  It
# is used to track what is new in order to create commit messages.
#
# merge.<sourcebranch> = <targetbranch> specifies merges to attempt; if
# git reports a successful merge with a 0 return code, the merge will
# be pushed.  This merge will be done after operations that modify
# <sourcebranch>, such as importing a cvs branch into git, or another
# merge operation.  Typical usage is therefore:
# merge.cvs-foo = bar baz
# merge.bar = master
# This would mean that when the "foo" branch is imported from cvs, it
# will be merged onto the "bar" and "baz" branches in git; furthermore,
# if the merge onto "bar" is successful, "bar" will then be merged onto
# "master".
#
# When doing a git branch export with preimport = true, if there are any
# merge failures from the preimport, then the git branch export will be
# aborted.
#
# All hooks are run in the obvious directory; git hooks are run in a
# git working directory with the specified branch checked out, and
# cvs hooks are run in a cvs checkout in which the specified branch
# is a sticky tag.  The pre hooks are run before a commit operation,
# and post hooks are run after all post-commit operations are complete;
# for example, the cvs post hooks are run after fast-forwarding the
# export- branch.  Git post hooks are run before merging downstream
# branches, and Git post hooks (but not pre hooks at this time; this
# may be changed later) are run for each merge target as well as for
# cvs import branches.
#l
# Per-branch hooks (e.g. prehook.git.master) are run in addition to
# general hooks (e.g. prehook.git) and the general hooks are run
# first.  Per-direction hooks (e.g. prehook.imp.git,
# prehook.imp.git.master) are are run after their bidirectional
# equivalents.
#
# Hooks that modify Git state are generally discouraged.  Committing
# may invalidate invariants and cause unexpected operation.  Changing
# branches will almost certainly break.  The main use for pre hooks
# is to normalize the contents of files to be committed in ways that
# are not implemented as specific configuration.  The main use for
# post hooks is arbitrary notification.
#
# Can later extend if necessary to add branch-specific skeleton.branchname
# and email.branchname to override defaults.
#
# basename of git repositories must be unique

import config
import os
import shlex

class RepositoryConfig(config.Config):
    def __init__(self, configFileName):
        config.Config.__init__(self, configFileName)
        # enforce uniqueness
        repos = {}
        for r in self.getRepositories():
            name = self.getRepositoryName(r)
            if name in repos:
                raise KeyError('Duplicate repository name %s: %s and %s'
                               %(name, repos[name], r))
            repos[name] = r
        self.requireAbsolutePaths('skeleton')

    def getDefault(self, section, key, error=True):
        if self.has_option(section, key):
            return self.get(section, key)
        if self.has_option('GLOBAL', key):
            return self.get('GLOBAL', key)
        if not error:
            return None
        # raise contextually meaningful NoOptionError using self.get
        self.get(section, key)

    def getOptional(self, section, key):
        if self.has_option(section, key):
            return self.get(section, key)
        return None

    def getRepositories(self):
        return set(self.sections()) - set(('GLOBAL',))

    @staticmethod
    def getRepositoryName(repository):
        return os.path.basename(repository)

    def getCVSRoot(self, repository, username):
        return ':pserver:%s%s' %(username, self.getDefault(repository, 'cvsroot'))

    def getGitRef(self, repository):
        return ':'.join((self.getDefault(repository, 'gitroot'), repository))

    def getCVSPath(self, repository):
        return self.get(repository, 'cvspath')

    def getSkeleton(self, repository):
        return self.getDefault(repository, 'skeleton', error=False)

    def getBranchFrom(self, repository):
        return self.getOptional(repository, 'branchfrom')

    def getBranchPrefix(self, repository, branch):
        optname = 'prefix.'+branch
        return self.getOptional(repository, optname)

    def getImportBranchMaps(self, repository):
        'return: [(cvsbranch, gitbranch), ...]'
        return [(x[4:], 'cvs-' + self.get(repository, x))
                 for x in sorted(self.options(repository))
                 if x.startswith('cvs.')]

    def getExportBranchMaps(self, repository):
        'return: [(gitbranch, cvsbranch, exportbranch), ...]'
        return [(x[4:], self.get(repository, x), 'export-' + x[4:])
                 for x in sorted(self.options(repository))
                 if x.startswith('git.')]

    def getMergeBranchMaps(self, repository):
        'return: {sourcebranch, set(targetbranch, targetbranch, ...), ...}'
        return dict((x[6:], set(self.get(repository, x).strip().split()))
                    for x in sorted(self.options(repository))
                    if x.startswith('merge.'))

    def getHook(self, type, when, repository):
        return self.getDefault(repository, when+'hook.'+type, error=False)

    def getHookDir(self, direction, type, when, repository):
        if direction:
            return self.getDefault(repository, when+'hook.'+direction+'.'+type,
                                   error=False)
        return None

    def getHookBranch(self, type, when, repository, branch):
        return self.getDefault(repository, when+'hook.'+type+'.'+branch,
                               error=False)

    def getHookDirBranch(self, direction, type, when, repository, branch):
        if direction:
            return self.getDefault(repository, when+'hook.'+direction+'.'+type+'.'+branch,
                                   error=False)
        return None

    def getHooksBranch(self, type, direction, when, repository, branch):
        return [shlex.split(x) for x in
                (self.getHook(type, when, repository),
                 self.getHookDir(direction, type, when, repository),
                 self.getHookBranch(type, when, repository, branch),
                 self.getHookDirBranch(direction, type, when, repository, branch))
                if x]

    def getGitImpPreHooks(self, repository, branch):
        return self.getHooksBranch('git', 'imp', 'pre', repository, branch)

    def getGitImpPostHooks(self, repository, branch):
        return self.getHooksBranch('git', 'imp', 'post', repository, branch)

    def getGitExpPreHooks(self, repository, branch):
        return self.getHooksBranch('git', 'exp', 'pre', repository, branch)

    def getGitExpPostHooks(self, repository, branch):
        return self.getHooksBranch('git', 'exp', 'post', repository, branch)

    def getCVSPreHooks(self, repository, branch):
        return self.getHooksBranch('cvs', None, 'pre', repository, branch)

    def getCVSPostHooks(self, repository, branch):
        return self.getHooksBranch('cvs', None, 'post', repository, branch)

    def getEmail(self, repository):
        email = self.getDefault(repository, 'email', error=False)
        if email:
            return email.split()
        return None
