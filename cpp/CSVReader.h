#pragma once
#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <iostream>
#include <iomanip>

class CSVReader {
    
public:
    static std::vector<std::vector<std::string>>
    readCSV(const std::string& path) {
        std::vector<std::vector<std::string>> data;
        std::ifstream file(path);
        
        if (!file.is_open()) {
            return data;
        }
        
        // Read the file line by line
        std::string line;
        while (std::getline(file, line)) {
            std::vector<std::string> row;
            std::stringstream ss(line);
            std::string cell;
            
            while (std::getline(ss, cell, ',')) {
                row.push_back(cell);
            }
            
            if (!row.empty()) {
                data.push_back(row);
            }
        }
        
        file.close();
        return data;
    }
    
    static void displayData(const std::vector<std::vector<std::string>>& data) {
        if (data.empty()) {
            std::cout << "No data to display." << std::endl;
            return;
        }
        
        // Calculate column widths
        std::vector<size_t> colWidths;
        for (size_t col = 0; col < data[0].size(); col++) {
            size_t maxWidth = 0;
            for (const auto& row : data) {
                if (col < row.size()) {
                    maxWidth = std::max(maxWidth, row[col].length());
                }
            }
            colWidths.push_back(maxWidth);
        }
        
        // Print each row
        for (const auto& row : data) {
            for (size_t col = 0; col < row.size(); col++) {
                std::cout << std::left << std::setw(colWidths[col] + 2) << row[col];
            }
            std::cout << std::endl;
        }
    }
};