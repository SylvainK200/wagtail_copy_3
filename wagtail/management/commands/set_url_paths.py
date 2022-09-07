from django.core.management.base import BaseCommand

from wagtail.models import Page


class Command(BaseCommand):

    help = "Resets url_path fields on each page recursively"

    def set_subtree(self, root, parent=None):
        if parent:
            root.url_path = parent.url_path + root.slug + "/"
        else:
            root.url_path = "/" + root.slug + "/"

        root.save()

        for child in root.get_children():
            self.set_subtree(child, root)


    def handle(self, *args, **options):
        for node in Page.get_root_nodes():
            self.set_subtree(node)
