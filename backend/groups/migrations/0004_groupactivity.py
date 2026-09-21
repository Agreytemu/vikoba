# Generated for the group workspace activity timeline.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0003_vikobagroup_country_vikobagroup_region_grouprolevote_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("MEMBER_JOINED", "Member joined"),
                            ("MEMBER_INVITED", "Member invited"),
                            ("SHARE_PURCHASED", "Share purchased"),
                            ("CONTRIBUTION_RECORDED", "Contribution recorded"),
                            ("CONTRIBUTION_UPDATED", "Contribution updated"),
                            ("ROLE_CHANGED", "Role changed"),
                        ],
                        max_length=40,
                    ),
                ),
                ("title", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="group_activities",
                        to="members.member",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activities",
                        to="groups.vikobagroup",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
