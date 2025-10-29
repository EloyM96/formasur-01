IF DB_ID(N'$(DB_NAME)') IS NULL
BEGIN
    DECLARE @sql nvarchar(MAX) = N'CREATE DATABASE [' + REPLACE('$(DB_NAME)', ']', ']]') + N']';
    EXEC (@sql);
END;
GO
