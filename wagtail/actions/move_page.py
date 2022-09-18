import logging

from django.core.exceptions import PermissionDenied
from django.db import transaction
from treebeard.mp_tree import MP_MoveHandler

from wagtail.log_actions import log
from wagtail.signals import post_page_move, pre_page_move

logger = logging.getLogger("wagtail")


class MovePagePermissionError(PermissionDenied):
    """
    Raised when the page move cannot be performed due to insufficient permissions.
    """

    pass


class MovePageAction:
    def __init__(self, page, target, pos=None, user=None):
        self.page = page
        self.target = target
        self.pos = pos
        self.user = user

    def check(self, parent_after, skip_permission_checks=False):
        if self.user and not skip_permission_checks:
            if not self.page.permissions_for_user(self.user).can_move_to(parent_after):
                raise MovePagePermissionError(
                    "You do not have permission to move the page to the target specified."
                )

    def _move_page(self, page, target, parent_after):
        from wagtail.models import Page

        # Determine old and new url_paths
        # Fetching new object to avoid affecting `page`
        page = Page.objects.get(id=page.id)
        old_url_path = page.url_path
        old_depth = page.depth

        # Fetching new object to avoid affecting `page`
        page = Page.objects.get(id=page.id)
        new_url_path = page.get_url_path(parent_after)

        # Determine new depth
        new_depth = len(new_url_path.split("/")) - 2

        # Update the page's depth
        page.depth = new_depth
        page.save()

        # Determine which pages need to be updated
        pages_to_update = Page.objects.filter(
            depth__gte=old_depth, url_path__startswith=old_url_path
        )

        # Update url_paths and depths
        for page_to_update in pages_to_update:
            page_to_update.url_path = new_url_path + page_to_update.url_path[
                len(old_url_path) :
            ]
            page_to_update.depth = new_depth + (page_to_update.depth - old_depth)
            page_to_update.save()

        # Move the page
        with transaction.atomic():
            pre_page_move.send(
                sender=page.specific_class, instance=page, target=target, pos=self.pos
            )
            MP_MoveHandler().move(page, target, pos=self.pos)
            post_page_move.send(
                sender=page.specific_class, instance=page, target=target, pos=self.pos
            )

        # Log the action
        log(
            "wagtail.pages.move",
            pages={
                "page": page.id,
                "old_parent": page.get_parent().id,
                "new_parent": parent_after.id,
            },
            user=self.user,
        )

        return page
        

    def execute(self, skip_permission_checks=False):
        if self.pos in ("first-child", "last-child", "sorted-child"):
            parent_after = self.target
        else:
            parent_after = self.target.get_parent()

        self.check(parent_after, skip_permission_checks=skip_permission_checks)

        return self._move_page(self.page, self.target, parent_after)
