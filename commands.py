# commands.py
import click
import csv
from flask.cli import with_appcontext
from sqlalchemy.exc import IntegrityError

# Import db and models from your extensions or app structure
from extensions import db
import models

# Helper function to find or create an item (prevents duplicates)
def get_or_create(session, model, defaults=None, **kwargs):
    """
    Checks if an instance of 'model' exists based on 'kwargs'.
    If it exists, returns the instance.
    If not, creates a new instance with 'kwargs' and 'defaults'.
    Returns the instance and a boolean indicating if it was created.
    """
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:
        # kwargs contains the unique identifiers, defaults contains other fields
        params = {**kwargs, **(defaults or {})}
        instance = model(**params)
        try:
            session.add(instance)
            session.commit()
            return instance, True
        except IntegrityError:
            # This can happen in a race condition or if the session is out of sync
            print("IntegrityError during get_or_create, rolling back and querying again.")
            session.rollback()
            instance = session.query(model).filter_by(**kwargs).first()
            return instance, False
        except Exception as e:
            print(f"Error during get_or_create for {model.__name__} with params {params}: {e}")
            session.rollback()
            raise e


@click.command('import-curriculum')
@click.argument('csv_filepath')
@with_appcontext
def import_curriculum(csv_filepath):
    """
    Imports curriculum data from a specified CSV file.

    CSV File must have columns: Subject, Grade, Strand, SubStrand, ItemType, ItemText
    ItemType must be 'LearningOutcome' or 'KeyInquiryQuestion'.
    """
    print(f"Starting curriculum import from: {csv_filepath}")
    processed_count = 0
    created_counts = {
        'Subject': 0, 'Grade': 0, 'Strand': 0, 'SubStrand': 0,
        'LearningOutcome': 0, 'KeyInquiryQuestion': 0
    }
    error_count = 0

    try:
        with open(csv_filepath, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            if not all(col in reader.fieldnames for col in ['Subject', 'Grade', 'Strand', 'SubStrand', 'ItemType', 'ItemText']):
                click.echo(click.style("Error: CSV file missing required columns (Subject, Grade, Strand, SubStrand, ItemType, ItemText)", fg='red'))
                return

            for row in reader:
                processed_count += 1
                try:
                    subject_name = row.get('Subject', '').strip()
                    grade_name = row.get('Grade', '').strip()
                    strand_name = row.get('Strand', '').strip()
                    substrand_name = row.get('SubStrand', '').strip()
                    item_type = row.get('ItemType', '').strip()
                    item_text = row.get('ItemText', '').strip()

                    if not all([subject_name, grade_name, strand_name, substrand_name, item_type, item_text]):
                        print(f"Skipping row {processed_count}: Missing data in one or more required fields.")
                        error_count += 1
                        continue

                    # 1. Subject (unique by name)
                    subject, created = get_or_create(db.session, models.Subject, name=subject_name)
                    if created: created_counts['Subject'] += 1

                    # 2. Grade (unique by name)
                    grade, created = get_or_create(db.session, models.Grade, name=grade_name)
                    if created: created_counts['Grade'] += 1

                    # 3. Strand (unique by name, subject_id, grade_id)
                    # --- THIS IS THE CORRECTED LOGIC ---
                    strand, created = get_or_create(db.session, models.Strand,
                                                    name=strand_name,
                                                    subject_id=subject.id,
                                                    grade_id=grade.id)
                    if created: created_counts['Strand'] += 1

                    # 4. SubStrand (unique by name, strand_id)
                    # --- THIS IS THE CORRECTED LOGIC ---
                    substrand, created = get_or_create(db.session, models.SubStrand,
                                                       name=substrand_name,
                                                       strand_id=strand.id)
                    if created: created_counts['SubStrand'] += 1

                    # 5. Learning Outcome or Key Inquiry Question
                    if item_type == 'LearningOutcome':
                        # Unique by description and substrand_id
                        lo, created = get_or_create(db.session, models.LearningOutcome,
                                                    substrand_id=substrand.id,
                                                    description=item_text)
                        if created: created_counts['LearningOutcome'] += 1
                    elif item_type == 'KeyInquiryQuestion':
                        # Unique by question_text and substrand_id
                        kiq, created = get_or_create(db.session, models.KeyInquiryQuestion,
                                                     substrand_id=substrand.id,
                                                     question_text=item_text)
                        if created: created_counts['KeyInquiryQuestion'] += 1
                    else:
                        print(f"Skipping row {processed_count}: Invalid ItemType '{item_type}'. Must be 'LearningOutcome' or 'KeyInquiryQuestion'.")
                        error_count += 1
                        continue

                except Exception as e:
                    db.session.rollback()
                    print(f"Error processing row {processed_count}: {e}")
                    print(f"Row data: {row}")
                    error_count += 1

    except FileNotFoundError:
        click.echo(click.style(f"Error: File not found at {csv_filepath}", fg='red'))
        return
    except Exception as e:
        db.session.rollback()
        click.echo(click.style(f"An unexpected error occurred: {e}", fg='red'))
        error_count += 1

    # --- Report Summary ---
    print("\n--- Import Summary ---")
    print(f"Total rows processed: {processed_count}")
    print(f"Errors encountered: {error_count}")
    print("New items created:")
    for item, count in created_counts.items():
        print(f"- {item}: {count}")
    print("----------------------")
    if error_count > 0:
        print(click.style("Import completed with errors.", fg='yellow'))
    else:
        print(click.style("Import completed successfully!", fg='green'))


def register_commands(app):
    """Registers CLI commands with the Flask app."""
    app.cli.add_command(import_curriculum)
    print("Registered CLI command: import-curriculum")