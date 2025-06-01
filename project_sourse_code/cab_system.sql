CREATE DATABASE IF NOT EXISTS cab_system;
USE cab_system;

CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100),
  email VARCHAR(100) UNIQUE,
  password VARCHAR(100),
  phone VARCHAR(20)
);

CREATE TABLE drivers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100),
  phone VARCHAR(20) UNIQUE,
  location VARCHAR(100),
  is_available BOOLEAN DEFAULT FALSE
);

CREATE TABLE rides (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT,
  driver_id INT,
  pickup VARCHAR(100),
  time DATETIME,
  fare INT,
  FOREIGN KEY(user_id)   REFERENCES users(id),
  FOREIGN KEY(driver_id) REFERENCES drivers(id)
);

-- Seed 4 drivers
INSERT INTO drivers (name,phone,location) VALUES
 ('Arun','7777000001','Central Bus Stand'),
 ('Kumar','7777000002','Chathiram Bus Stand'),
 ('Aravind','7777000003','Srirangam'),
 ('Ram','7777000004','TVS Tollgate');
ALTER TABLE rides ADD COLUMN status VARCHAR(20) DEFAULT 'pending';
