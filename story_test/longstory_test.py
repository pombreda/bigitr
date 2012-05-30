from cStringIO import StringIO
import mock
import os
import tempfile
import unittest

from gitcvs import cvsimport, context, git, cvs

class TestStory(unittest.TestCase):
    def setUp(self):
        self.oldcwd = os.getcwd()
        self.workdir = tempfile.mkdtemp(suffix='.gitcvs')
        # for config
        self.logdir = self.workdir + '/log'
        os.makedirs(self.logdir)
        self.gitdir = self.workdir + '/git'
        os.makedirs(self.gitdir)
        self.cvsdir = self.workdir + '/cvs'
        os.makedirs(self.cvsdir)
        self.cvsroot = self.workdir + '/cvsroot'
        os.makedirs(self.cvsroot)
        # outside the system
        self.gitroot = self.workdir + '/gitroot'
        os.makedirs(self.gitroot + '/git')
        self.cvsco = self.workdir + '/cvsco'
        os.makedirs(self.cvsco)
        if 'CVSROOT' in os.environ:
            self.oldcvsroot = os.environ['CVSROOT']
        else:
            self.oldcvsroot = None
        os.unsetenv('CVSROOT')
        appConfig = StringIO('[global]\n'
                             'logdir = %s\n'
                             'gitdir = %s\n'
                             '[export]\n'
                             'cvsdir = %s\n'
                             %(self.logdir,
                               self.gitdir,
                               self.cvsdir)
                            )
        repConfig = StringIO('[GLOBAL]'
                             'cvsroot = %s\n'
                             'gitroot = %s/\n'
                             '[git/module1]\n'
                             'cvspath = module1\n'
                             'cvs.b1 = b1\n'
                             'cvs.b2 = b2\n'
                             'git.master = b2\n'
                             'git.b1 = b1\n'
                             '[git/module2]\n'
                             'cvspath = module2\n'
                             'cvs.b1 = b1\n'
                             % (self.cvsroot,
                                self.gitroot)
                             )
        self.ctx = context.Context(appConfig, repConfig)
        self.getCVSRoot = self.ctx.getCVSRoot
        self.getGitRef = self.ctx.getGitRef
        self.ctx.getCVSRoot = mock.Mock()
        self.ctx.getCVSRoot.return_value = self.cvsroot
        self.ctx.getGitRef = lambda(a): '/'.join((self.gitroot, a))

    @staticmethod
    def removeRecursive(dir):
        for b, dirs, files in os.walk(dir, topdown=False):
            for f in files:
                os.remove('/'.join((b, f)))
            for d in dirs:
                os.rmdir('/'.join((b, d)))
        os.removedirs(dir)

    def tearDown(self):
        os.chdir(self.oldcwd)
        self.removeRecursive(self.workdir)
        if self.oldcvsroot:
            os.environ['CVSROOT'] = self.oldcvsroot
        else:
            os.unsetenv('CVSROOT')
        self.ctx.getCVSRoot = self.getCVSRoot
        self.ctx.getGitRef = self.getGitRef

    def unpack(self, tarball):
        os.system('tar -x -C %s -z -f %s/testdata/%s' %(
                  self.workdir,
                  os.environ['BASEDIR'],
                  tarball))

    def pack(self, tarball):
        tarball = '/'.join((os.environ['BASEDIR'], 'testdata', tarball))
        if not os.path.exists(tarball):
            # do not pack log (unnecessary) or git, cvsco (workdir changes)
            os.system('tar -c -C %s -z -f %s gitroot cvs cvsroot'
                      %(self.workdir, tarball))

    def test_lowlevel1(self):
        self.unpack('TESTROOT.1.tar.gz')
        imp = cvsimport.Importer(self.ctx, 'johndoe')
        Git = git.Git(self.ctx, 'git/module1')
        CVS = cvs.CVS(self.ctx, 'git/module1', 'b1', imp.username)
        # the tool otherwise assumes that the remote repository exists
        os.system('git init --bare %s/git/module1' %self.gitroot)
        imp.importcvs('git/module1', Git, CVS, 'b1', 'cvs-b1')
        self.assertTrue(os.path.exists(self.gitdir + '/module1/1'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/2'))
        self.assertFalse(os.path.exists(self.gitdir + '/module1/3'))

        # now test with no changes in CVS
        imp.importcvs('git/module1', Git, CVS, 'b1', 'cvs-b1')
        self.assertTrue(os.path.exists(self.gitdir + '/module1/1'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/2'))
        self.assertFalse(os.path.exists(self.gitdir + '/module1/3'))

        os.system('cd %s; CVSROOT=%s cvs co -r b1 module1'
                  %(self.cvsco, self.cvsroot))
        file(self.cvsco + '/module1/3', 'w').write('3\n')
        os.system('cd %s/module1; cvs add 3; cvs commit -m "add 3"'
                  %self.cvsco)

        imp.importcvs('git/module1', Git, CVS, 'b1', 'cvs-b1')
        self.assertTrue(os.path.exists(self.gitdir + '/module1/1'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/2'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/3'))
        self.assertEqual(file(self.gitdir + '/module1/3').read(), '3\n')

        # now test with no changes in CVS
        imp.importcvs('git/module1', Git, CVS, 'b1', 'cvs-b1')
        self.assertTrue(os.path.exists(self.gitdir + '/module1/1'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/2'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/3'))
        self.assertEqual(file(self.gitdir + '/module1/3').read(), '3\n')

        os.system('cd %s/module1; cvs tag -b b2' %self.cvsco)
        file(self.cvsco + '/module1/4', 'w').write('4\n')
        os.system('cd %s/module1; cvs add 4; cvs commit -r b2 -m "add 4";'
                  'cvs up -r b2'
                  %self.cvsco)

        # make sure that the new CVS branch does not break the old one
        imp.importcvs('git/module1', Git, CVS, 'b1', 'cvs-b1')
        self.assertTrue(os.path.exists(self.gitdir + '/module1/1'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/2'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/3'))
        self.assertEqual(file(self.gitdir + '/module1/3').read(), '3\n')
        self.assertFalse(os.path.exists(self.gitdir + '/module1/4'))

        # new CVS branch requires separate CVS object that knows about it
        CVS2 = cvs.CVS(self.ctx, 'git/module1', 'b2', imp.username)
        imp.importcvs('git/module1', Git, CVS2, 'b2', 'cvs-b2')
        self.assertTrue(os.path.exists(self.gitdir + '/module1/1'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/2'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/3'))
        self.assertEqual(file(self.gitdir + '/module1/3').read(), '3\n')
        self.assertEqual(file(self.gitdir + '/module1/4').read(), '4\n')

        # test importing the removal of a file
        os.remove(self.cvsco + '/module1/3')
        os.system('cd %s/module1; cvs remove 3;'
                  ' cvs commit -m "removed 3 in b2"' %self.cvsco)
        imp.importcvs('git/module1', Git, CVS2, 'b2', 'cvs-b2')
        self.assertTrue(os.path.exists(self.gitdir + '/module1/1'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/2'))
        self.assertFalse(os.path.exists(self.gitdir + '/module1/3'))
        self.assertEqual(file(self.gitdir + '/module1/4').read(), '4\n')

        # make sure that removal on new CVS branch does not break the old one
        imp.importcvs('git/module1', Git, CVS, 'b1', 'cvs-b1')
        self.assertTrue(os.path.exists(self.gitdir + '/module1/1'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/2'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/3'))
        self.assertEqual(file(self.gitdir + '/module1/3').read(), '3\n')
        self.assertFalse(os.path.exists(self.gitdir + '/module1/4'))

        # and change branch again
        imp.importcvs('git/module1', Git, CVS2, 'b2', 'cvs-b2')
        self.assertTrue(os.path.exists(self.gitdir + '/module1/1'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/2'))
        self.assertFalse(os.path.exists(self.gitdir + '/module1/3'))
        self.assertEqual(file(self.gitdir + '/module1/4').read(), '4\n')

        # make sure that nothing conflicts with another module
        Gitm2 = git.Git(self.ctx, 'git/module2')
        CVSm2 = cvs.CVS(self.ctx, 'git/module2', 'b1', imp.username)
        # the tool otherwise assumes that the remote repository exists
        os.system('git init --bare %s/git/module2' %self.gitroot)
        imp.importcvs('git/module2', Gitm2, CVSm2, 'b1', 'cvs-b1')
        self.assertTrue(os.path.exists(self.gitdir + '/module2/1'))
        self.pack('TESTROOT.2.tar.gz')

    def test_lowlevel2(self):
        'test updating multiple branches in multiple repositories together'
        self.unpack('TESTROOT.2.tar.gz')
        imp = cvsimport.Importer(self.ctx, 'johndoe')
        Git = git.Git(self.ctx, 'git/module1')
        # set up work directory
        imp.importAll()

        # now make a bunch of changes, and ensure that they are all
        # imported by calling importAll once
        os.system('cd %s; CVSROOT=%s cvs co -r b1 module1'
                  %(self.cvsco, self.cvsroot))
        os.system('cd %s/module1; '
                  'cvs up -r b1; '
                  'touch b1.1; '
                  'cvs add b1.1; '
                  'cvs commit -r b1 -m "added b1.1 to b1"; '
                  'cvs up -r b2; '
                  'touch b2.1; '
                  'cvs add b2.1; '
                  'cvs commit -r b2 -m "added b2.1 to b2"; '
                  %self.cvsco)
        os.system('cd %s; CVSROOT=%s cvs co -r b1 module2'
                  %(self.cvsco, self.cvsroot))
        os.system('cd %s/module2; '
                  'touch 9; '
                  'cvs add 9 ; '
                  'cvs commit -m "added 9"; '
                  %self.cvsco)
        imp.importAll()
        self.assertTrue(os.path.exists(self.gitdir + '/module2/9'))
        os.system('cd %s/module1; git checkout cvs-b1' %self.gitdir)
        self.assertTrue(os.path.exists(self.gitdir + '/module1/b1.1'))
        self.assertFalse(os.path.exists(self.gitdir + '/module1/b2.1'))
        os.system('cd %s/module1; git checkout cvs-b2' %self.gitdir)
        self.assertFalse(os.path.exists(self.gitdir + '/module1/b1.1'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/b2.1'))
        self.pack('TESTROOT.3.tar.gz')

    def test_lowlevel3(self):
        'test imports onto merged branches'
        self.unpack('TESTROOT.3.tar.gz')
        imp = cvsimport.Importer(self.ctx, 'johndoe')
        Git = git.Git(self.ctx, 'git/module1')
        # set up work directory
        imp.importBranches('git/module1', Git)

        os.system('cd %s/module1; '
                  'git branch b1 cvs-b1; '
                  'git branch master cvs-b2; '
                  'git checkout master; '
                  'git merge b1 -s ours -m "setting start point for b1 merge"; '
                  'git push origin master; '
                  'git push origin b1; '
                  %self.gitdir)

        os.system('cd %s; CVSROOT=%s cvs co -r b1 module1'
                  %(self.cvsco, self.cvsroot))
        os.system('cd %s/module1; '
                  'cvs up -r b1; '
                  'touch b1.2; '
                  'cvs add b1.2; '
                  'cvs commit -r b1 -m "added b1.2 to b1"; '
                  'cvs up -r b2; '
                  'touch b2.2; '
                  'cvs add b2.2; '
                  'cvs commit -r b2 -m "added b2.2 to b2"; '
                  %self.cvsco)
        imp.importAll()
        os.system('cd %s/module1; git checkout cvs-b1' %self.gitdir)
        self.assertTrue(os.path.exists(self.gitdir + '/module1/b1.2'))
        self.assertFalse(os.path.exists(self.gitdir + '/module1/b2.2'))
        os.system('cd %s/module1; git checkout cvs-b2' %self.gitdir)
        self.assertFalse(os.path.exists(self.gitdir + '/module1/b1.2'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/b2.2'))

        os.system('cd %s/module1; '
                  'git checkout master; '
                  'git merge cvs-b2 -m "latest changes from cvs b2"; '
                  'git merge cvs-b1 -m "latest merge from cvs b1"; '
                  'git push origin master; '
                  %self.gitdir)
        self.assertTrue(os.path.exists(self.gitdir + '/module1/b1.2'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/b2.2'))
        self.assertFalse(os.path.exists(self.gitdir + '/module1/b1.1'))
        self.assertTrue(os.path.exists(self.gitdir + '/module1/b2.2'))

        self.pack('TESTROOT.4.tar.gz')

    def test_lowlevel4Junk(self):
        'test throwing away junk in the git directory'
        self.unpack('TESTROOT.4.tar.gz')
        imp = cvsimport.Importer(self.ctx, 'johndoe')
        Git = git.Git(self.ctx, 'git/module1')
        CVS = cvs.CVS(self.ctx, 'git/module1', 'b1', imp.username)
        # set up work directory
        imp.importcvs('git/module1', Git, CVS, 'b1', 'cvs-b1')
        file('%s/module1/transient' %self.gitdir, 'w')
        imp.importcvs('git/module1', Git, CVS, 'b1', 'cvs-b1')
        self.assertFalse(os.path.exists(self.gitdir + '/module1/transient'))

        # do not need to pack anything, since no changes have been made