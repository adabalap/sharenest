import oci

# Configure the OCI client
config = oci.config.from_file()  # Uses ~/.oci/config by default
object_storage = oci.object_storage.ObjectStorageClient(config)

# Replace with your namespace and bucket name
namespace_name = "axmvidnvowmd"
bucket_name    = "sharenest"

try:
    # List objects in the bucket
    objects = object_storage.list_objects(namespace_name, bucket_name)

    # Print object names
    print(f"Objects in bucket '{bucket_name}':")
    for obj in objects.data.objects:
        print(obj.name)

except oci.exceptions.ServiceError as e:
    print(f"Error: {e}")

