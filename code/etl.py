import configparser
from datetime import datetime
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, col
from pyspark.sql.functions import year, month, dayofmonth, hour, weekofyear, date_format,dayofweek


config = configparser.ConfigParser()
config.read('dl.cfg')

os.environ['AWS_ACCESS_KEY_ID']=config['AWS_ACCESS_KEY_ID']
os.environ['AWS_SECRET_ACCESS_KEY']=config['AWS_SECRET_ACCESS_KEY']


def create_spark_session():
    """
        Create a Spark Session
    """
    spark = SparkSession \
        .builder \
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:2.7.0") \
        .getOrCreate()
    return spark


def process_song_data(spark, input_data, output_data):
     """
        Description: This function loads song_data from S3 and processes it by extracting the songs and artist tables
        and then again loaded back to S3
        
        Parameters:
            spark       : Spark Session
            input_data  : location of song_data json files with the songs metadata
            output_data : S3 bucket were dimensional tables in parquet format will be stored
    """
    # get filepath to song data file
    song_data_file = input_data + "song_data/*/*/*/*.json" 
    song_data = spark.read.json(song_data_file )
    
    
    # read song data file
    df = song_data.select(['song_id', 'title', 'artist_id', 'year', 'duration'])

    # extract columns to create songs table
    songs_table = df.dropDuplicates()
    
    # write songs table to parquet files partitioned by year and artist
    songs_table.write.partitionBy(['year','artist_id']).parquet(output_data + "songs.parquet")

    # extract columns to create artists table
    artists_table = song_data.select([song_data.artist_id, \
                                song_data.artist_name.alias('name'), \
                                song_data.artist_location.alias('location'), \
                                song_data.artist_latitude.alias('latitude'), \
                                song_data.artist_longitude.alias('longitude')]).dropDuplicates()
    
    # write artists table to parquet files
    artists_table.write.parquet(output_data + "artists.parquet")


def process_log_data(spark, input_data, output_data):
     """
        Description: This function loads log_data from S3 and processes it by extracting the songs and artist tables
        and then again loaded back to S3.
        
        Parameters:
            spark       : Spark Session
            input_data  : location of log_data json files with the events data
            output_data : S3 bucket were dimensional tables in parquet format will be stored
            
    """
    # get filepath to log data file
    log_data = input_data +'log_data/*/*/*.json'

    # read log data file
    df = spark.read.json(log_data)
    
    # filter by actions for song plays
    df = df.filter(df.page == "NextSong")

    # extract columns for users table    
    users_table = df.select([df.userId.alias('user_id'), \
                             df.firstName.alias('first_name'), \
                             df.lastName.alias('last_name'), \
                             df.gender, \
                             df.level]).dropDuplicates()
    
    # write users table to parquet files
    users_table.write.parquet(output_data + 'users.parquet')

    # create timestamp column from original timestamp column
 
    
    # create datetime column from original timestamp column
    get_datetime = udf( lambda x : datetime.fromtimestamp(x/1000.0).strftime('%Y-%m-%d %H:%M:%S'))
    df = df.withColumn('start_time', get_datetime(df.ts)) 
    
    # extract columns to create time table
    time_table = df.select(df.start_time.alias('start_time'), \
                hour(df.start_time).alias('hour'),\
                dayofmonth(df.start_time).alias('day'),\
                weekofyear(df.start_time).alias('week'),\
                month(df.start_time).alias('month'),\
                year(df.start_time).alias('year'),
                dayofweek(df.start_time).alias('weekday')).dropDuplicates()
    
    
    # write time table to parquet files partitioned by year and month
    time_table.write.partitionBy('year','month').parquet(output_data + 'time.parquet')

    # read in song data to use for songplays table
    song_df = spark.read.json('s3a://udacity-dend/song_data/*/*/*/*.json')
    df.createOrReplaceTempView('log_table')
    song_df.createOrReplaceTempView('song_table')
    

    # extract columns from joined song and log datasets to create songplays table 
    songplays_table = spark.sql("""select row_number() over (order by log_table.start_time) as songplay_id,
                                      log_table.start_time,
                                      year(log_table.start_time) year,
                                      month(log_table.start_time) month,
                                      log_table.userId as user_id,
                                      log_table.level,
                                      song_table.song_id,
                                      song_table.artist_id,
                                      log_table.sessionId as session_id,
                                      log_table.location,
                                      log_table.userAgent as user_agent
                                      from log_table 
                                      join song_table 
                                      on (log_table.artist = song_table.artist_name and
                                          log_table.song = song_table.title and
                                          log_table.length = song_table.duration )""")

    # write songplays table to parquet files partitioned by year and month
    songplays_table.write.partitionBy(['year','month']).parquet(output_data + 'songplay.parquet')


def main():
    """
        Extract songs and events data from S3, Transform it into dimensional tables format, and Load it back to S3 in Parquet format
    """
    spark = create_spark_session()
    input_data = "s3a://udacity-dend/"
    output_data = "s3a://anudatalake/"
    
    process_song_data(spark, input_data, output_data)    
    process_log_data(spark, input_data, output_data)


if __name__ == "__main__":
    main()
