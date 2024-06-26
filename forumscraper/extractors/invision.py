# by Dominik Stanisław Suchora <suchora.dominik7@gmail.com>
# License: GNU GPLv3

import re
import json
from reliq import reliq

from ..utils import dict_add
from .common import ItemExtractor, ForumExtractor


class invision(ForumExtractor):
    class User(ItemExtractor):
        def __init__(self, session):
            super().__init__(session)

            self.match = [
                re.compile(r"/(.*/)?(\d+)(-[^/]*)?/?"),
                2,
            ]
            self.path_format = "m-{}"
            self.trim = True

        def get_url(self, url):
            url_delim = "?"
            if url.find("?") != -1:
                url_delim = "&"

            return "{}{}do=hovercard".format(url, url_delim)

        def get_first_html(self, url, rq=None, **kwargs):
            kwargs["headers"].update({"X-Requested-With": "XMLHttpRequest"})
            return self.session.get_html(url, self.trim, **kwargs)

        def get_contents(self, rq, url, u_id, **kwargs):
            ret = {"format_version": "invision-user", "url": url, "id": u_id}

            t = json.loads(
                rq.search(
                    r"""
                .name h2 class=b>"ipsType_reset ipsType_"; a | "%i",
                .background div .ipsCoverPhoto_container; img src | "%(src)v",
                .avatar img src .ipsUserPhoto | "%(src)v",
                .group p class="ipsType_reset ipsType_normal"; * c@[0] | "%i",

                .joined {
                    p class="ipsType_reset ipsType_medium ipsType_light" m@b>"Joined "; time datetime | "%(datetime)v",
                    div .cUserHovercard_data; li m@">Joined<"; time datetime | "%(datetime)v"
                },

                .lastseen {
                    p class="ipsType_reset ipsType_medium ipsType_light" m@b>"Last visited "; time datetime | "%(datetime)v",
                    div .cUserHovercard_data; li m@">Last visited<"; time datetime | "%(datetime)v"
                },

                .info dl; div l@[1]; {
                    .name dt | "%i",
                    .value dd | "%i"
                } | ,
                div class=b>"ipsFlex ipsFlex-ai:center "; div class="ipsFlex ipsFlex-ai:center"; {
                    .rank img title | "%(title)v",
                    .rank_date time datetime | "%(datetime)v",
                }
                .badges.a div class=b>"ipsFlex ipsFlex-ai:center "; ul; li; img alt | "%(alt)v\n"
            """
                )
            )
            dict_add(ret, t)
            return ret

    class Thread(ItemExtractor):
        def __init__(self, session):
            super().__init__(session)

            self.match = [
                re.compile(r"/(.*/)?(\d+)(-[^/]*)?/?"),
                2,
            ]
            self.trim = True

        def get_poll_answers(self, rq):
            ret = []
            for i in rq.filter(r"ul; li").children():
                el = {}
                el["option"] = i.search(r'div .ipsGrid_span4 | "%i"')
                el["votes"] = i.search(
                    r'div .ipsGrid_span1; * m@E>"^(<[^>]*>[^<]*</[^>]*>)?[^<]+$" | "%i" / sed "s/^<i.*<\/i> //"'
                )
                ret.append(el)
            return ret

        def get_poll_questions(self, rq):
            ret = []
            for i in rq.filter(r"ol .ipsList_reset .cPollList; li l@[1]").children():
                el = {}
                el["question"] = i.search(r'h3; span | "%i"')
                el["answers"] = self.get_poll_answers(i)
                ret.append(el)

            return ret

        def get_poll(self, rq):
            ret = {}
            controller = rq.filter(r"section data-controller=core.front.core.poll")

            title = ""
            questions = []

            if controller:
                title = controller.search(
                    r'h2 l@[1]; span l@[1] | "%i" / sed "s/<.*//;s/&nbsp;//g;s/ *$//"'
                )
                questions = self.get_poll_questions(controller)

            ret["title"] = title
            ret["questions"] = questions
            return ret

        def get_reactions_details(self, rq, **kwargs):
            ret = []
            nexturl = rq.search(
                r'ul .ipsReact_reactions; li .ipsReact_reactCount; [0] a href | "%(href)v" / sed "s/&amp;/\&/g; s/&reaction=.*$//;q" "E"'
            )

            while True:
                if len(nexturl) == 0:
                    break

                rq = self.session.get_html(
                    nexturl,
                    True,
                    headers={"X-Requested-With": "XMLHttpRequest"},
                    **kwargs,
                )

                t = json.loads(
                    rq.search(
                        r"""
                    .reactions ol; li; {
                        .avatar a .ipsUserPhoto; img src | "%(src)v",
                        a .ipsType_break href; {
                            .user_link * l@[0] | "%(href)v",
                            .user * l@[0] | "%i"
                        },
                        .reaction span .ipsType_light; img src | "%(src)v" / sed "s#.*/reactions/##;s/\..*//;s/^react_//",
                        .date time datetime | "%(datetime)v"
                    } |
                """
                    )
                )
                ret += t["reactions"]

                nexturl = rq.search(
                    r'li .ipsPagination_next -.ipsPagination_inactive; [0] a href | "%(href)v" / sed "s/&amp;/&/; s/&reaction=.*$//;q"'
                )
            return ret

        def get_contents(self, rq, url, t_id, **kwargs):
            ret = {"format_version": "invision-thread", "url": url, "id": t_id}
            page = 0

            t = json.loads(
                rq.search(
                    r"""
                div #ipsLayout_mainArea; h1 class="ipsType_pageTitle ipsContained_container"; {
                    .title span class="ipsType_break ipsContained"; span -class | "%i",
                    .badges.a span title | "%(title)v\n"
                },
                .rating.b ul .ipsRating_collective; li .ipsRating_on | "true",
                div .ipsPageHeader; {
                    .user_link a .ipsType_break href | "%(href)v",
                    .user a .ipsType_break href; * c@[0] | "%i",
                    .user_avatar a .ipsUserPhoto; img src | "%(src)v",
                    .user_followers a .ipsFollow; span .ipsCommentCount | "%i",
                },
                .date div .ipsFlex-flex:11; time datetime | "%(datetime)v",
                .path.a nav class=b>"ipsBreadcrumb ipsBreadcrumb_top "; ul data-role="breadcrumbList"; li; a; span | "%t\n" / sed "s/ $//",

                .tags.a {
                    div .ipsPageHeader; ul .ipsTags; a; span c@[0] | "%i",
                    div #ipsLayout_mainArea; h1 class="ipsType_pageTitle ipsContained_container"; a .ipsTag_prefix rel=tag; span c@[0] | "%i",
                },

                .warning div .cTopicPostArea; span .ipsType_warning | "%i",
            """
                )
            )
            dict_add(ret, t)

            ret["poll"] = self.get_poll(rq)

            t = json.loads(
                rq.search(
                    r"""
                .recommended div data-role=recommendedComments; div .ipsBox data-commentID; {
                    .id.u div .ipsBox data-commentID | "%(data-commentID)v",
                     div .ipsReactOverview; {
                        .reactions.a ul; li; img alt | "%(alt)v\n",
                        .reaction_count.u p class="ipsType_reset ipsType_center" | "%i"
                    },
                    .user_avatar aside; img src | "%(src)v",
                    div .ipsColumn; {
                        * .ipsComment_meta; {
                            .user_link a .ipsType_break href | "%(href)v",
                            .user a .ipsType_break href; * c@[0] | "%i",
                            .date time datetime | "%(datetime)v"
                        },
                        .link a .ipsButton href | "%(href)v",
                        a .ipsType_break href c@[0] l@[1]; {
                            .ruser_link a l@[0] | "%(href)v",
                            .ruser a l@[0] | "%i"
                        },
                        .content div .ipsType_richText | "%i"
                    }
                }
            """
                )
            )
            dict_add(ret, t)

            expr = reliq.expr(
                r"""
                .id.u article #B>elComment_[0-9]* | "%(id)v\n" / sed "s/^elComment_//",
                aside; {
                    .user h3 class=b>"ipsType_sectionHead cAuthorPane_author "; * c@[0] [0] | "%i",
                    * .cAuthorPane_photo data-role=photo {
                        .user_avatar a .ipsUserPhoto; img src | "%(src)v",
                        .badges.a {
                            img title alt | "%(alt)v\n",
                            span .cAuthorPane_badge title=e>" joined recently" | "%(title)v\n"
                        }
                    },
                    ul .cAuthorPane_info; {
                        .group li data-role=group; * c@[0] | "%i",
                        .group_icon li data-role=group-icon; img src | "%(src)v",
                        .rank_title li data-role=rank-title | "%i",
                        .rank_image li data-role=rank-image; * | "%i",
                        .reputation_badge li data-role=reputation-badge; span | "%i" / sed "s/^<i .*<\/i> //;s/,//g;q",
                        .posts li data-role=posts | "%i" / sed "s/ .*//;s/,//g",
                        .custom li data-role=custom-field | "%i",
                        .user_info.a ul .ipsList_reset; li; a title l@[1] | "%(title)v\n" / sort "u",
                    }
                },
                div .ipsComment_meta; {
                    .top_badges.a div class=a>"ipsComment_badges"; ul .ipsList_reset; li; strong | "%i\n" / sed "s#<i [^>]*></i> ##g",
                    .date time datetime | "%(datetime)v",
                },
                .content div .cPost_contentWrap; div data-role=commentContent | "%i",
                .signature div data-role=memberSignature; div data-ipslazyload | "%i",
            """
            )
            posts = []

            while True:
                for i in rq.filter(r"article #B>elComment_[0-9]*").children():
                    post = {}

                    post["user_link"] = i.search(
                        r'aside; h3 class=b>"ipsType_sectionHead cAuthorPane_author "; a href | "%(href)v"'
                    )

                    user_link = post["user_link"]
                    if not kwargs["nousers"] and len(user_link) > 0:
                        try:
                            self.user.get(user_link, **kwargs)
                        except self.common_exceptions as ex:
                            self.handle_error(ex, user_link, True, **kwargs)

                    t = json.loads(i.search(expr))
                    dict_add(post, t)

                    t = json.loads(
                        i.search(
                            r"""
                        ul .ipsReact_reactions; {
                            .reactions_users li .ipsReact_overview; a href -href=a>?do= l@[1]; {
                                .link * l@[0] | "%(href)v",
                                .name * l@[0] | "%i"
                            } | ,
                            .reactions_temp.a li .ipsReact_reactCount; span a@[0] / sed "s/<span><img .* alt=\"//; s/\".*//; N; s/\n/\t/; s/<span>//; s/<\/span>//"
                        }
                    """
                        )
                    )
                    t["reactions"] = []
                    for j in t["reactions_temp"]:
                        el = {}
                        reaction = j.split("\t")
                        el["name"] = reaction[0]
                        el["count"] = reaction[1]
                        t["reactions"].append(el)
                    t.pop("reactions_temp")
                    dict_add(post, t)

                    reactions_details = []
                    if not kwargs["noreactions"]:
                        try:
                            reactions_details = self.get_reactions_details(i)
                        except self.common_exceptions as ex:
                            self.handle_error(ex, i, True, **kwargs)
                    post["reactions_details"] = reactions_details

                    posts.append(post)

                page += 1
                if (
                    kwargs["thread_pages_max"] != 0
                    and page >= kwargs["thread_pages_max"]
                ):
                    break
                nexturl = rq.search(
                    r'ul .ipsPagination [0]; li .ipsPagination_next -.ipsPagination_inactive; a | "%(href)v" / sed "s#/page/([0-9]+)/.*#/?page=\1#" "E"'
                )
                if len(nexturl) == 0:
                    break
                rq = self.session.get_html(nexturl, True, **kwargs)

            ret["posts"] = posts
            return ret

    def __init__(self, session=None, **kwargs):
        super().__init__(session, **kwargs)

        self.trim = True

        self.thread = self.Thread(self.session)
        self.user = self.User(self.session)
        self.thread.user = self.user

        self.board_forums_expr = reliq.expr(
            r'li class=b>"cForumRow ipsDataItem "; div .ipsDataItem_main; h4; a href | "%(href)v\n", div .ipsForumGrid; a .cForumGrid__hero-link href | "%(href)v\n"'
        )
        self.forum_forums_expr = self.board_forums_expr
        self.forum_threads_expr = reliq.expr(
            r'ol data-role=tableRows; h4; a class="" href=e>"/" | "%(href)v\n"'
        )
        self.guesslist = [
            {
                "func": "get_thread",
                "exprs": [r"^/(.*[/?])?(thread|topic)s?/"],
            },
            {
                "func": "get_forum",
                "exprs": [r"^/(.*[/?])?forums?/"],
            },
            {"func": "get_board", "exprs": None},
        ]

    def get_forum_next(self, rq):
        return rq.search(
            'ul .ipsPagination; li .ipsPagination_next -.ipsPagination_inactive; [0] a | "%(href)v"'
        )
