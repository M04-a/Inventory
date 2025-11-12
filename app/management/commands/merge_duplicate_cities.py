"""
Management command to merge duplicate cities (with and without diacritics)
Usage: python manage.py merge_duplicate_cities
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from app.models import City, Building, Item
from app.utils import normalize_city_name


class Command(BaseCommand):
    help = 'Merge duplicate cities (e.g., Timișoara and Timisoara into one)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Get all cities
        cities = City.objects.all()

        # Group cities by normalized name
        normalized_groups = {}
        for city in cities:
            normalized_name = normalize_city_name(city.name)
            if normalized_name not in normalized_groups:
                normalized_groups[normalized_name] = []
            normalized_groups[normalized_name].append(city)

        # Find duplicates
        duplicates_found = 0
        merged_count = 0

        for normalized_name, city_list in normalized_groups.items():
            if len(city_list) > 1:
                duplicates_found += 1
                self.stdout.write(
                    self.style.WARNING(f'\nFound {len(city_list)} cities that normalize to "{normalized_name}":')
                )

                for city in city_list:
                    building_count = city.buildings.count()
                    item_count = Item.objects.filter(building_ref__city=city).count()
                    self.stdout.write(f'  - ID {city.id}: "{city.name}" ({building_count} buildings, {item_count} items)')

                # Keep the first one (or the one without diacritics if exists)
                cities_without_diacritics = [c for c in city_list if c.name == normalized_name]
                if cities_without_diacritics:
                    primary_city = cities_without_diacritics[0]
                else:
                    primary_city = city_list[0]

                cities_to_merge = [c for c in city_list if c.id != primary_city.id]

                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Keeping: ID {primary_city.id} "{primary_city.name}"')
                )

                for duplicate_city in cities_to_merge:
                    self.stdout.write(
                        self.style.WARNING(f'  ✗ Merging: ID {duplicate_city.id} "{duplicate_city.name}"')
                    )

                    if not dry_run:
                        with transaction.atomic():
                            buildings_moved = 0
                            buildings_merged = 0

                            # Process each building from the duplicate city
                            for building in duplicate_city.buildings.all():
                                # Check if a building with the same name exists in primary city
                                existing_building = Building.objects.filter(
                                    city=primary_city,
                                    name=building.name
                                ).first()

                                if existing_building:
                                    # Merge: move all items to the existing building
                                    items_to_move = Item.objects.filter(building_ref=building)
                                    items_count = items_to_move.count()

                                    if items_count > 0:
                                        items_to_move.update(
                                            building_ref=existing_building,
                                            city=primary_city.name,
                                            building=existing_building.name,
                                            address=existing_building.address,
                                            lat=existing_building.lat,
                                            lng=existing_building.lng
                                        )
                                        self.stdout.write(
                                            f'      → Merged building "{building.name}": moved {items_count} items to existing building'
                                        )

                                    # Delete the duplicate building
                                    building.delete()
                                    buildings_merged += 1
                                else:
                                    # No conflict: just move the building
                                    building.city = primary_city
                                    building.save()
                                    buildings_moved += 1

                            # Update old text fields in Item model for items that didn't have building_ref
                            items_updated = Item.objects.filter(city=duplicate_city.name).update(
                                city=primary_city.name
                            )

                            # Delete the duplicate city
                            duplicate_city.delete()

                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'    → Moved {buildings_moved} buildings, merged {buildings_merged} buildings, '
                                    f'updated {items_updated} text-only items'
                                )
                            )
                            merged_count += 1

        # Summary
        self.stdout.write('\n' + '=' * 60)
        if duplicates_found == 0:
            self.stdout.write(self.style.SUCCESS('✓ No duplicate cities found!'))
        else:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f'Found {duplicates_found} groups of duplicate cities.\n'
                        f'Run without --dry-run to merge them.'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Successfully merged {merged_count} duplicate cities!'
                    )
                )

