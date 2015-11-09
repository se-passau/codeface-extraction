# coding=utf-8
"""
This file is able to extract developer--artifact relations from the Codeface database.
"""

import logging

from os.path import join as pathjoin, exists as pathexists
from os import makedirs

from codeface.dbmanager import DBManager
from codeface.configuration import Configuration

logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel("INFO")


def __select_list_of_authors(dbm, project):
    dbm.doExec("""
                    SELECT pers.id AS id, pers.name AS name

                    FROM project p

                    # add authors/developers/persons
                    JOIN person pers
                    ON p.id = pers.projectId

                    # filter for current release range and artifact
                    WHERE p.name = '%s'

                    ORDER BY pers.id ASC

                    # LIMIT 10
               """ %
               project
               )

    list_of_authors = dbm.doFetchAll()
    return list_of_authors


def get_list_of_authors(dbm, project, range_resdir):
    """
    Selects the list of authors for the given project, using the database-manager parameter.
    Afterwards, the pairs (author_id, author_name) are written to the file 'authors.list' in range_resdir.

    :param dbm: the database manager to use
    :param project: the project name to search
    :param range_resdir: the desired release range of the project
    """

    # get authors for given project
    list_of_authors = __select_list_of_authors(dbm, project)

    # convert to a proper list for file writing
    lines = ["{}; {}\n".format(dev_id, dev_name) for dev_id, dev_name in list_of_authors]

    # write lines to file
    outfile = pathjoin(range_resdir, "authors.list")
    f = open(outfile, 'w')
    f.writelines(lines)
    f.close()


def __select_artifacts_per_author(dbm, project, tagging, revision, entitytype="FEATURE"):
    dbm.doExec("""
                    SELECT pers.id AS id, pers.name AS name, cd.entityId AS artifact

                    FROM project p

                    # get release range for projects
                    JOIN release_range r ON p.id = r.projectId

                    # start of range
                    JOIN release_timeline l1 ON r.releaseStartId = l1.id
                    # end of range
                    JOIN release_timeline l2 ON r.releaseEndId = l2.id

                    # add commits for the ranges
                    JOIN commit c on r.id = c.releaseRangeId

                    # add meta-data for commits
                    JOIN commit_dependency cd ON c.id = cd.commitId

                    # add authors/developers/persons
                    JOIN person pers ON c.author = pers.id

                    # filter for current release range and artifact
                    WHERE p.name = '%s'
                    AND p.analysisMethod = '%s'
                    AND l2.tag = '%s'
                    AND cd.entityType = '%s'

                    GROUP BY name, artifact ASC
                    ORDER BY id, artifact ASC

                    # LIMIT 10
                """ %
               (project, tagging, revision, entitytype)
               )

    authors_to_artifacts = dbm.doFetchAll()
    return authors_to_artifacts


def get_artifacts_per_author(dbm, project, tagging, kind, end_rev, artifact, range_resdir):
    """
    Selects the list of artifacts per developer for the given project, tagging, and release range, using the
    database-manager parameter. The kind of artifact is defined by the kind parameter. Afterwards, the pairs
    (author_name, artifact_name) are written to the file '[kind].list' in range_resdir.

    :param dbm: the database manager to use
    :param project: the project name to search
    :param tagging: the tagging analysis for the current project
    :param kind: the current extraction to run, also name of output file
    :param end_rev: the release tag defining the end of a release range
    :param artifact: the kind of artifact to search for
    :param range_resdir: the desired release range of the project
    """

    # get artifact information per author
    authors_to_artifacts = __select_artifacts_per_author(dbm, project, tagging, end_rev, artifact)

    # convert a2a to tuples (id, artifact)
    lines = ["{}; {}\n".format(dev_name, art) for dev_id, dev_name, art in authors_to_artifacts]

    # write lines to file for current kind of artifact (e.g., authors2feature, authors2function)
    outfile = pathjoin(range_resdir, kind + ".list")
    f = open(outfile, 'w')
    f.writelines(lines)
    f.close()


def __select_artifacts_per_commit(dbm, project, tagging, revision, entitytype="FEATURE"):
    dbm.doExec("""
                    SELECT c.id, cd.entityId AS artifact

                    FROM project p

                    # get release range for projects
                    JOIN release_range r
                    ON p.id = r.projectId

                    # start of range
                    JOIN release_timeline l1
                    ON r.releaseStartId = l1.id
                    # end of range
                    JOIN release_timeline l2
                    ON r.releaseEndId = l2.id

                    # add commits for the ranges
                    JOIN commit c
                    on r.id = c.releaseRangeId

                    # add meta-data for commits
                    JOIN commit_dependency cd
                    ON c.id = cd.commitId

                    # add authors/developers/persons
                    JOIN person pers
                    ON c.author = pers.id

                    # filter for current release range and artifact
                    WHERE p.name = '%s'
                    AND p.analysisMethod = '%s'
                    AND l2.tag = '%s'
                    AND cd.entityType = '%s'

                    ORDER BY c.id, cd.entityId

                    # LIMIT 10
                """ %
               (project, tagging, revision, entitytype)
               )

    authors_to_artifacts = dbm.doFetchAll()
    return authors_to_artifacts


def get_cochanged_artifacts(dbm, project, tagging, end_rev, artifact, range_resdir):
    """
    Selects the list of touched artifacts per commit for the given project, tagging, and release range, using the
    database-manager parameter. Afterwards, the sets are written
     to the file 'cochanged-artifacts.list' in range_resdir.

    :param dbm: the database manager to use
    :param project: the project name to search
    :param tagging: the tagging analysis for the current project
    :param end_rev: the release tag defining the end of a release range
    :param artifact: the kind of artifact to search for
    :param range_resdir: the desired release range of the project
    """

    # get list of changed artifacts per author
    commit2artifact = __select_artifacts_per_commit(dbm, project, tagging, end_rev, artifact)

    # convert c2a to tuples (commit, artifact)
    lines = ["{}; {}\n".format(commit_id, art) for commit_id, art in commit2artifact]

    # write lines to file for current kind of artifact
    outfile = pathjoin(range_resdir, "commit2" + artifact.lower() + ".list")
    f = open(outfile, 'w')
    f.writelines(lines)
    f.close()


def __select_mailing_authors(dbm, project, tagging, revision):
    dbm.doExec("""
                    SELECT el.fromId, el.toId, SUM(el.weight) as weight

                    FROM project p

                    # get release range for projects
                    JOIN release_range r
                    ON p.id = r.projectId

                    # start of range
                    JOIN release_timeline l1
                    ON r.releaseStartId = l1.id
                    # end of range
                    JOIN release_timeline l2
                    ON r.releaseEndId = l2.id

                    # add cluster analysis
                    JOIN cluster c
                    ON r.id = c.releaseRangeId
                    # and corresponding edgelist
                    JOIN edgelist el
                    ON el.clusterId = c.id

                    # add authors/developers/persons
                    JOIN person p1
                    ON el.fromId = p1.id
                    JOIN person p2
                    ON el.toId = p2.id

                    # filter for current release range and artifact
                    WHERE p.name = '%s'
                    AND p.analysisMethod = '%s'
                    AND l2.tag = '%s'
                    AND c.clusterMethod = "email"

                    GROUP BY p1.id, p2.id
                    ORDER BY p1.id ASC, p2.id ASC

                    # LIMIT 10
                """ %
               (project, tagging, revision)
               )

    authors_to_artifacts = dbm.doFetchAll()
    return authors_to_artifacts


def get_mailing_authors(dbm, project, tagging, end_rev, range_resdir):
    """
    Selects the list of author pairs that exchange e-mails for the given project, tagging, and release range, using the
    database-manager parameter. Afterwards, the sets are written to the file 'authors_emailing.list' in range_resdir.

    :param dbm: the database manager to use
    :param project: the project name to search
    :param tagging: the tagging analysis for the current project
    :param end_rev: the release tag defining the end of a release range
    :param range_resdir: the desired release range of the project
    """

    # get list of changed artifacts per author
    author2author = __select_mailing_authors(dbm, project, tagging, end_rev)

    # convert a2a to edgelist
    lines = ["{}; {}; {}\n".format(author_from, author_to, weight) for author_from, author_to, weight in author2author]

    # write lines to file for current kind of artifact
    #fixme use a separate mail folder?!
    outfile = pathjoin(range_resdir, "authors.network.mailinglist.list")
    f = open(outfile, 'w')
    f.writelines(lines)
    f.close()


##
# RUN FOR ALL PROJECTS
##

def run_extraction(systems, artifact2tagging, codeface_conf, project_conf, resdir):
    """
    Runs the extraction process for the list of given parameters.

    :param systems: the list of software systems analyzed by Codeface, e.g., 'busybox'
    :param artifact2tagging: a dict mapping extraction-process names to the kind of artifact to extract;
           e.g., 'author2feature':'FEATURE'
    :param codeface_conf: the Codeface configuration to load
    :param project_conf: the project configuration to load (for release ranges)
    :param resdir: the Codeface results dir, where output files are written
    """

    # for all kinds of artifacts
    for kind, (artifact, tagging) in artifact2tagging.iteritems():

        # for all projects
        for current_system in systems:

            log.info("%s: Extracting '%s' from '%s' analysis" % (current_system, artifact, tagging))

            # load configuration and initialize database manager
            conf = Configuration.load(codeface_conf, project_conf.format(current_system, tagging))
            dbm = DBManager(conf)

            # get setting for current combination
            project = conf["project"]
            revs = conf["revisions"]
            project_resdir = pathjoin(resdir, current_system, tagging)

            # for all revisions of this project
            for i in range(len(revs) - 1):
                start_rev = revs[i]
                end_rev = revs[i + 1]

                # print (project, tagging, kind, start_rev, end_rev)

                # results directory for current revision
                range_resdir = pathjoin(project_resdir, "{0}-{1}".format(start_rev, end_rev))
                if not pathexists(range_resdir):
                    makedirs(range_resdir)

                # get_artifacts_per_author(dbm, project, tagging, kind, end_rev, artifact, range_resdir)
                get_list_of_authors(dbm, project, range_resdir)

                # further extractions
                # get_cochanged_artifacts(dbm, project, tagging, end_rev, artifact, range_resdir)

                # extract mailing-list analysis (associated with proximity projects!)
                if tagging == 'proximity':
                    log.info("%s: Extracting mailing network from '%s_%s' for version '%s'" % (
                        current_system, current_system, tagging, end_rev))
                    get_mailing_authors(dbm, project, tagging, end_rev, range_resdir)


if __name__ == '__main__':
    ##
    # CONSTANTS
    ##

    __systems = ["busybox"]  # ["sqlite", "sqlite", "tcl", "linux", "openssl"]
    #  FIXME run all analyses again. completely.

    # kind: (artifact, tagging)
    __artifact2tagging = {
        'author2feature': ("Feature", 'feature'),
        'author2function': ("Function", 'proximity'),
        'author2featureexpression': ('FeatureExpression', 'feature')
        # 'author2file':  ("file", "proximity")  # FIXME implement author2file (needs new SELECT)
    }

    ##
    # CONSTRUCT PATHS
    ##

    # __cf_vm = "/local/hunsen/codeface"
    __cf_vm = "/home/codeface"

    __cf_dir = pathjoin(__cf_vm, "codeface-repo")

    __resdir = pathjoin(__cf_vm, "results")
    __codeface_conf = pathjoin(__cf_dir, "codeface.conf")
    __project_conf = pathjoin(__cf_dir, "conf/spl/{}_{}.conf")

    run_extraction(__systems, __artifact2tagging, __codeface_conf, __project_conf, __resdir)