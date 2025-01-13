import psycopg2
import xmlrpc.client
from pprint import pprint
import json
from tqdm import tqdm
odoo_url = "https://jcyared.odoo.com/"
database  = "jcyaredodoo-v131-master-751420"
api_key = "24b5e4ab9d52994d15fd7d98b015e488365d6f12"
username = "dataengineering@jcyared.com"
password = "dataeng@Y2red123"


# PostgreSQL configuration
psgs_host = "database-odoo-tbls.cveg8qk2u6ev.us-east-1.rds.amazonaws.com"
psgs_dbname = "postgres"
psgs_user = "postgres"
psgs_password = "Munich38"
psgs_port = 5432
RedShift_db="dev"
RedShift_admin="adminmobin"

# Map Odoo field types to PostgreSQL data types
odoo_to_postgresql_type_map = {
    'char': 'VARCHAR',                # Short text fields
    'text': 'TEXT',                   # Long text fields
    'integer': 'INTEGER',             # Whole numbers
    'float': 'DOUBLE PRECISION',      # Decimal numbers
    'boolean': 'BOOLEAN',             # True/False values
    'date': 'DATE',                   # Date-only values
    'datetime': 'TIMESTAMP',          # Date and time values
    'many2one': 'INTEGER',            # Foreign key reference (ID of related record)
    'one2many': 'TEXT',               # JSON or array (if storing relationships as text)
    'many2many': 'TEXT',              # JSON or array for relationships
    'binary': 'BOOLEAN',                # Binary data, e.g., images or files
    'selection': 'VARCHAR',           # Dropdown fields with predefined options
    'monetary': 'NUMERIC(18, 2)',     # Monetary values with precision
    'reference': 'VARCHAR',           # Polymorphic relation (table name and ID)
    'html': 'TEXT',                   # HTML content
    'json': 'JSONB',                  # JSON data structure
    'jsonb': 'JSONB',                 # JSONB for better indexing support
    'decimal': 'NUMERIC',             # High-precision decimal values
    'array': 'TEXT[]',                # Array of text (or adapt to type-specific arrays)
    'priority': 'INTEGER',            # Priority levels as integers
}


# common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(odoo_url))
common = xmlrpc.client.ServerProxy(f'{odoo_url}/xmlrpc/2/common')
version_db=common.version()
print(version_db)
uid = common.authenticate(database, username, password, {})
if uid:
    print("Authentication successful")
else:
    print("Authentication failed")
    exit()


models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(odoo_url))

# Connect to PostgreSQL
try:
    conn = psycopg2.connect(
        dbname=psgs_dbname,
        user=psgs_user,
        password=psgs_password,
        host=psgs_host,
        port=psgs_port
    )
    cursor = conn.cursor()
    print("Connected to PostgreSQL")
except Exception as e:
    print(f"Failed to connect to PostgreSQL: {e}")
    exit()

# all_models = [
#         "account.move",
#         "account.move.line", "product.product", "product.template",
#         # "purchase.order", "purchase.order.line", "res.currency", "res.currency.rate",
#         # "res.partner", "sale.order", "sale.order.discount", "sale.order.line",
#         # "stock.move", "stock.move.line"
#     ]

all_models = [
        "account.account",
        "account.journal", "account.tax",
    ]

# Function to create table in PostgreSQL
def create_table(model, fields_metadata):
    table_name = model.replace('.', '_')  # Replace dots with underscores for compatibility
    column_definitions = []
    
    for field_name, field_info in fields_metadata.items():
        column_type = odoo_to_postgresql_type_map.get(field_info.get('type'), 'TEXT')
        column_definitions.append(f'"{field_name}" {column_type}')
    
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        {', '.join(column_definitions)}
    );
    """
    cursor.execute(create_table_sql)
    conn.commit()
    print(f"Table {table_name} created/verified in PostgreSQL")



def fetch_and_insert_data(model, fields_metadata, table_name):
    limit = 1000
    offset = 0
    fields_to_fetch = list(fields_metadata.keys())  # Start with all fields

    fields_to_exclude = ['stock', 'byproduct', 'needed_terms', 'land', 'currency_rate'
                         ,'cumulated_balance', 'balance', 'credit', 'debit','sequence', 'account_id', 'parent_state',
                         'move_name', 'move_id', 'analytic_precision']

    # Filter out fields with substrings in fields_to_exclude
    fields_to_fetch = [field for field in fields_to_fetch if not any(ex in field for ex in fields_to_exclude)]

    # allowed_fields = []
    # for field in fields_to_fetch:
    #     try:
    #         # Test access to the field
    #         models.execute_kw(
    #             database, uid, password,
    #             'account.move', 'search_read',
    #             [[]], {'fields': [field], 'limit': 1}
    #         )
    #         allowed_fields.append(field)
    #     except Exception as e:
    #         print(f"Field {field} excluded: {e}")

    # print(f"Allowed fields for fetching: {allowed_fields}")


    while True:
        try:
            has_access = models.execute_kw(
            database, uid, password,
            model, 'check_access_rights',
            ['read'], {'raise_exception': False}
            )
            if not has_access:
                print(f"Skipping {model}: No read access")
                continue
            else:
                print(f"Access to {model} model: {has_access}")
            # Fetch a batch of records
            records = models.execute_kw(
                database, uid, password,
                model, 'search_read',
                [[]],  # No filters, fetch all records
                {
                    'fields': fields_to_fetch,  # Fields to fetch
                    'limit': limit,  # Number of rows to fetch in each batch
                    'offset': offset  # Start fetching from this row
                }
            )
            if not records:
                break  # Exit the loop when no more records are found

            print(f"Fetched {len(records)} records from {model} (Offset: {offset})")

            # Insert fetched records into PostgreSQL
            insert_data_batch(table_name, records, fields_metadata)

            offset += limit  # Move to the next batch
            print(f"Offset Done: {offset}")
        except xmlrpc.client.Fault as fault:
            print(f"Cautch error in xmlrpc.client.Fault 1")
            # print(f"Error while fetching data for {model}: {fault}")
            # print(f"fields_to_fetch: {fields_to_fetch}")
            # Handle field-specific permission error
            if "not allowed to access" in str(fault):
                # Extract the problematic field name from the error message
                error_message = str(fault)
                field_name = None
                for field in fields_to_fetch:
                    if field in error_message:
                        field_name = field
                        break
                
                if field_name:
                    print(f"Skipping field '{field_name}' in model '{model}' due to permission error")
                    fields_to_fetch.remove(field_name)  # Exclude the problematic field
                    continue  # Retry fetching with the updated fields list
                else:
                    print(f"Unidentified field causing error: {fault}")
                    break  # Exit if the field cannot be identified
            else:
                print(f"Error while fetching data for {model}: {fault}")
                break
        except Exception as e:
            print(f"MWError while fetching or inserting data for {model}: {e}")
            print(f"MWError while fetching data for {model}: {fault}")
            print(f"MWfields_to_fetch: {fields_to_fetch}")
            break

    
def prepare_record_for_insertion(record, fields_metadata):
    """
    Transform an Odoo record into a format compatible with PostgreSQL.
    """
    transformed_record = {}
    
    for field, value in record.items():
        field_type = fields_metadata.get(field, {}).get("type")
        
        if field_type == "many2one":
            # Use the ID (first element) from the many2one field
            transformed_record[field] = value[0] if value else None
        # elif field_type in ("one2many", "many2many") or isinstance(value, list) or any(substring in field for substring in ("json", "kanban")):
        elif field_type in ("one2many", "many2many"):
            # Convert list to PostgreSQL array format (optional handling)
            transformed_record[field] = "{" + ",".join(map(str, value)) + "}" if value else "{}"
        elif field_type == "date" and value is False:
            # Replace False with None for date fields
            transformed_record[field] = None
            
        elif field_type == "datetime" and value is False:
            # Replace False with None for date fields
            transformed_record[field] = None

        elif isinstance(value, dict):
            # Convert dictionary to JSON string
            transformed_record[field] = json.dumps(value)
        else:
            # Leave other field types as-is
            transformed_record[field] = value
    
    return transformed_record


# Function to check if a record exists
def record_exists(table_name, record_id):
    check_sql = f'SELECT 1 FROM {table_name} WHERE "id" = %s LIMIT 1;'
    cursor.execute(check_sql, (record_id,))
    return cursor.fetchone() is not None

def insert_data_batch(table_name, records, fields_metadata):
    """
    Insert a batch of records into the PostgreSQL table, skipping existing ones.
    """
    if not records:
        return
    existing_recoeds=[]
    with tqdm(total=len(records), desc=f"Inserting into {table_name}") as progress_bar:
        for record in records:
            record_id = record.get("id")
            # print(record_id)
            if record_exists(table_name, record_id):
                # print(f"record: {record_id} exist")
                existing_recoeds.append(record_id)
                progress_bar.update(1)
                continue
                
            # Transform the record into a PostgreSQL-compatible format
            transformed_record = prepare_record_for_insertion(record, fields_metadata)
            # Check if the record already exists
            # record_id = transformed_record.get("id")
            # if not record_exists(table_name, record_id):
            try:
                # Prepare the columns and values for insertion
                columns = ', '.join([f'"{key}"' for key in transformed_record.keys()])
                placeholders = ', '.join(['%s'] * len(transformed_record))
                insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders});"
                
                # Execute the insert query
                cursor.execute(insert_sql, list(transformed_record.values()))
            except Exception as e:
                print(f"metadata: {fields_metadata}")
                print(f"record: {record}")
                # pprint(record)
                print(f"transformed_record: {transformed_record}")
                print(f"Failed to insert record into {table_name}: {e}")
            
            # else:
            #     print(f"Record with id {record_id} already exists, skipping.")

            
            # Update the progress bar
            progress_bar.update(1)
            # break
        
    conn.commit()
    print(f"Processed {len(records)} records for table {table_name}.")
    print(f"Existing records skipped: {len(existing_recoeds)}")

def lambda_handler(event, context):
    # TODO implement
    # Main replication logic
    for model in all_models:
        print("start")
        # Fetch metadata for the model
        fields_metadata = models.execute_kw(
            database, uid, password,
            model, 'fields_get', [],
            {'attributes': ['string', 'type', 'help']}
        )
        # print(fields_metadata)
        # print()
        
        # Create table in PostgreSQL
        create_table(model, fields_metadata)
        table_name = model.replace('.', '_')

        # Fetch and insert data in batches
        fetch_and_insert_data(model, fields_metadata, table_name)

    # Close PostgreSQL connection
    cursor.close()
    conn.close()
    print("Replication completed and PostgreSQL connection closed")
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }

